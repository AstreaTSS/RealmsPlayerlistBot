import asyncio
import datetime
import importlib
import math
import typing

import attrs
import naff
from tortoise.expressions import Q

import common.models as models
import common.playerlist_utils as pl_utils
import common.utils as utils
from common.realms_api import RealmsAPIException


hours_ago_choices = [
    naff.SlashCommandChoice("1", "1"),  # type: ignore
    naff.SlashCommandChoice("2", "2"),  # type: ignore
    naff.SlashCommandChoice("3", "3"),  # type: ignore
    naff.SlashCommandChoice("4", "4"),  # type: ignore
    naff.SlashCommandChoice("5", "5"),  # type: ignore
    naff.SlashCommandChoice("6", "6"),  # type: ignore
    naff.SlashCommandChoice("7", "7"),  # type: ignore
    naff.SlashCommandChoice("8", "8"),  # type: ignore
    naff.SlashCommandChoice("9", "9"),  # type: ignore
    naff.SlashCommandChoice("10", "10"),  # type: ignore
    naff.SlashCommandChoice("11", "11"),  # type: ignore
    naff.SlashCommandChoice("12", "12"),  # type: ignore
    naff.SlashCommandChoice("13", "13"),  # type: ignore
    naff.SlashCommandChoice("14", "14"),  # type: ignore
    naff.SlashCommandChoice("15", "15"),  # type: ignore
    naff.SlashCommandChoice("16", "16"),  # type: ignore
    naff.SlashCommandChoice("17", "17"),  # type: ignore
    naff.SlashCommandChoice("18", "18"),  # type: ignore
    naff.SlashCommandChoice("19", "19"),  # type: ignore
    naff.SlashCommandChoice("20", "20"),  # type: ignore
    naff.SlashCommandChoice("21", "21"),  # type: ignore
    naff.SlashCommandChoice("22", "22"),  # type: ignore
    naff.SlashCommandChoice("23", "23"),  # type: ignore
    naff.SlashCommandChoice("24", "24"),  # type: ignore
]


def _convert_fields(value: tuple[str, ...]) -> tuple[str, ...]:
    return ("online", "last_seen") + value if value else ("online", "last_seen")


@attrs.define(kw_only=True)
class RealmPlayersContainer:
    realmplayers: list[models.RealmPlayer] = attrs.field()
    fields: tuple[str, ...] = attrs.field(default=None, converter=_convert_fields)


class Playerlist(utils.Extension):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.sem = asyncio.Semaphore(
            3
        )  # prevents bot from overloading xbox api, hopefully

        self._previous_now = datetime.datetime.now(tz=datetime.timezone.utc)
        self._realmplayer_queue: asyncio.Queue[RealmPlayersContainer] = asyncio.Queue()

        self.get_people_task = asyncio.create_task(self._start_get_people())
        self.upload_players_task = asyncio.create_task(self._upload_players())

    def drop(self):
        self.get_people_task.cancel()
        self.upload_players_task.cancel()
        super().drop()

    def _next_time(self):
        now = naff.Timestamp.utcnow()
        # margin of error
        multiplicity = math.ceil((now.timestamp() + 0.1) / 60)
        next_time = multiplicity * 60
        return naff.Timestamp.utcfromtimestamp(next_time)

    async def _start_get_people(self):
        await self.bot.fully_ready.wait()
        await utils.sleep_until(self._next_time())

        try:
            while True:
                next_time = self._next_time()
                await self._get_people_from_realms()
                await utils.sleep_until(next_time)
        except Exception as e:
            if not isinstance(e, asyncio.CancelledError):
                await utils.error_handle(self.bot, e)

    async def _get_people_from_realms(self):
        try:
            realms = await self.bot.realms.fetch_activities()
        except Exception as e:
            if isinstance(e, RealmsAPIException) and e.resp.status == 502:
                # bad gateway, can't do much about it
                return
            await utils.error_handle(self.bot, e)
            return

        player_objs: list[models.RealmPlayer] = []
        joined_player_objs: list[models.RealmPlayer] = []
        gotten_realm_ids: set[int] = set()
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        for realm in realms.servers:
            gotten_realm_ids.add(realm.id)
            player_set: set[str] = set()

            for player in realm.players:
                player_set.add(player.uuid)

                kwargs = {
                    "realm_xuid_id": f"{realm.id}-{player.uuid}",
                    "online": True,
                    "last_seen": now,
                }

                if player.uuid not in self.bot.online_cache[realm.id]:
                    kwargs["last_joined"] = now
                    joined_player_objs.append(models.RealmPlayer(**kwargs))
                else:
                    player_objs.append(models.RealmPlayer(**kwargs))

            left = self.bot.online_cache[realm.id].difference(player_set)
            self.bot.online_cache[realm.id] = player_set

            player_objs.extend(
                models.RealmPlayer(
                    realm_xuid_id=f"{realm.id}-{player}",
                    online=False,
                    last_seen=self._previous_now,
                )
                for player in left
            )

        online_cache_ids = set(self.bot.online_cache.keys())
        for missed_realm_id in online_cache_ids.difference(gotten_realm_ids):
            now_invalid = self.bot.online_cache[missed_realm_id]
            if not now_invalid:
                continue

            player_objs.extend(
                models.RealmPlayer(
                    realm_xuid_id=f"{missed_realm_id}-{player}",
                    online=False,
                    last_seen=self._previous_now,
                )
                for player in now_invalid
            )

            self.bot.online_cache[missed_realm_id] = set()

        self._previous_now = now

        # handle this in the "background" so we don't have to worry about this
        # taking too long
        await self._realmplayer_queue.put(
            RealmPlayersContainer(realmplayers=player_objs)
        )
        await self._realmplayer_queue.put(
            RealmPlayersContainer(
                realmplayers=joined_player_objs, fields=("last_joined",)
            )
        )

    async def _upload_players(self):
        while True:
            try:
                container = await self._realmplayer_queue.get()

                await models.RealmPlayer.bulk_create(
                    container.realmplayers,
                    on_conflict=("realm_xuid_id",),
                    update_fields=container.fields,
                )
            except Exception as e:
                if isinstance(e, asyncio.CancelledError):
                    return
                await utils.error_handle(self.bot, e)
            finally:
                if not self._realmplayer_queue.empty():
                    self._realmplayer_queue.task_done()

    async def get_players_from_realmplayers(
        self,
        realm_id: str,
        realmplayers: list[models.RealmPlayer],
    ):
        player_list: typing.List[pl_utils.Player] = []
        unresolved_dict: typing.Dict[str, pl_utils.Player] = {}

        for member in realmplayers:
            xuid = member.realm_xuid_id.removeprefix(f"{realm_id}-")

            player = pl_utils.Player(
                xuid,
                member.last_seen,
                member.online,
                await self.bot.redis.get(xuid),
                member.last_joined,
            )
            if player.resolved:
                player_list.append(player)
            else:
                unresolved_dict[xuid] = player

        if unresolved_dict:
            gamertag_handler = pl_utils.GamertagHandler(
                self.bot,
                self.sem,
                tuple(unresolved_dict.keys()),
                self.bot.profile,
                self.bot.openxbl_session,
            )
            gamertag_dict = await gamertag_handler.run()

            for xuid, gamertag in gamertag_dict.items():
                unresolved_dict[xuid].gamertag = gamertag

            player_list.extend(unresolved_dict.values())

        return player_list

    @naff.slash_command(
        name="playerlist",
        description="Sends a playerlist, a log of players who have joined and left.",
        default_member_permissions=naff.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )  # type: ignore
    @naff.check(pl_utils.can_run_playerlist)  # type: ignore
    @naff.cooldown(naff.Buckets.GUILD, 1, 240)  # type: ignore
    @naff.slash_option("hours_ago", "How far back the playerlist should go.", naff.OptionTypes.STRING, choices=hours_ago_choices)  # type: ignore
    async def playerlist(
        self,
        ctx: utils.RealmContext | utils.RealmPrefixedContext,
        hours_ago: str = "12",
        **kwargs,
    ):
        """Checks and makes a playerlist, a log of players who have joined and left.
        By default, the command version goes back 12 hours.
        If you wish for it to go back more, simply do `!?playerlist <# hours ago>`.
        The number provided should be in between 1-24 hours.
        The autorun version only goes back 2 hours.
        Has a cooldown of 4 minutes due to how intensive this command can be.
        May take a while to run at first.
        Requires Manage Server permissions."""

        init_mes = not kwargs.get("no_init_mes", False)

        guild_config = await ctx.fetch_config()

        if not bool(guild_config.club_id and guild_config.realm_id):
            if init_mes:
                raise utils.CustomCheckFailure(
                    "This bot isn't fully configured! Take a look at `/config help` for"
                    " how to configure the bot."
                )
            else:
                return

        actual_hours_ago: int = int(hours_ago)
        now = naff.Timestamp.utcnow()
        time_delta = datetime.timedelta(hours=actual_hours_ago)
        time_ago = now - time_delta

        realmplayers = await models.RealmPlayer.filter(
            Q(realm_xuid_id__startswith=f"{guild_config.realm_id}-"),
            Q(Q(online=True), Q(last_seen__gte=time_ago), join_type="OR"),
        )

        if not realmplayers:
            if init_mes:
                raise utils.CustomCheckFailure(
                    "No one seems to have been on the Realm for the last "
                    + f"{actual_hours_ago} hour(s). Make sure you haven't changed"
                    " Realms or kicked the bot's account - try relinking the Realm"
                    " via `/config link-realm` if that happens."
                )
            else:
                return

        player_list = await self.get_players_from_realmplayers(
            guild_config.realm_id, realmplayers  # type: ignore
        )

        online_list = sorted(
            (p.display for p in player_list if p.in_game), key=lambda g: g.lower()
        )
        offline_list = [
            p.display
            for p in sorted(
                player_list, key=lambda p: p.last_seen.timestamp(), reverse=True
            )
            if not p.in_game
        ]

        timestamp = naff.Timestamp.fromdatetime(self._previous_now)

        if online_list:
            embed = naff.Embed(
                color=self.bot.color,
                title="People online right now",
                description="\n".join(online_list),
                timestamp=timestamp,
            )
            embed.set_footer(text="As of")
            await ctx.send(embed=embed)

        if offline_list:
            # gets the offline list in lines of 25
            # basically, it's like
            # [ [list of 25 strings] [list of 25 strings] etc.]
            chunks = [offline_list[x : x + 25] for x in range(0, len(offline_list), 25)]

            first_embed = naff.Embed(
                color=naff.Color.from_hex("95a5a6"),
                description="\n".join(chunks[0]),
                title=f"People on in the last {actual_hours_ago} hour(s)",
                timestamp=timestamp,
            )
            first_embed.set_footer(text="As of")
            await ctx.send(embed=first_embed)

            for chunk in chunks[1:]:
                embed = naff.Embed(
                    color=naff.Color.from_hex("95a5a6"),
                    description="\n".join(chunk),
                    timestamp=timestamp,
                )
                embed.set_footer(text="As of")
                await ctx.send(embed=embed)
                await asyncio.sleep(0.2)

        if init_mes and not online_list and not offline_list:
            raise utils.CustomCheckFailure(
                "No one has been on the Realm for the last "
                + f"{actual_hours_ago} hour(s)."
            )

    @naff.slash_command("online", description="Allows you to see if anyone is online on the Realm right now.", dm_permission=False)  # type: ignore
    @naff.cooldown(naff.Buckets.GUILD, 1, 10)
    @naff.check(pl_utils.can_run_playerlist)  # type: ignore
    async def online(self, ctx: utils.RealmContext):
        """Allows you to see if anyone is online on the Realm right now."""
        # uses much of the same code as playerlist

        guild_config = await ctx.fetch_config()

        realmplayers = await models.RealmPlayer.filter(
            realm_xuid_id__startswith=f"{guild_config.realm_id}-", online=True
        )
        player_list = await self.get_players_from_realmplayers(
            guild_config.realm_id, realmplayers  # type: ignore
        )

        if online_list := sorted(
            (p.display for p in player_list if p.in_game), key=lambda g: g.lower()
        ):
            embed = naff.Embed(
                color=self.bot.color,
                title=f"{len(online_list)}/10 people online",
                description="\n".join(online_list),
                timestamp=naff.Timestamp.fromdatetime(self._previous_now),
            )
            embed.set_footer(text="As of")
            await ctx.send(embed=embed)
        else:
            raise utils.CustomCheckFailure("No one is on the Realm right now.")


def setup(bot):
    importlib.reload(utils)
    importlib.reload(pl_utils)
    Playerlist(bot)
