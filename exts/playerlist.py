import asyncio
import contextlib
import datetime
import importlib
import math
import typing
from collections import defaultdict

import aiohttp
import attr
import naff
import orjson
from pydantic import ValidationError
from tortoise.exceptions import DoesNotExist
from tortoise.expressions import Q
from xbox.webapi.api.provider.profile.models import ProfileResponse

import common.custom_providers as providers
import common.models as models
import common.utils as utils

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


@attr.s(slots=True, eq=False)
class Player:
    """A simple class to represent a player on a Realm."""

    xuid: str = attr.ib()
    last_seen: datetime.datetime = attr.ib()
    in_game: bool = attr.ib(default=False)
    gamertag: typing.Optional[str] = attr.ib(default=None)

    def __eq__(self, o: object) -> bool:
        return o.xuid == self.xuid if isinstance(o, self.__class__) else False

    @property
    def resolved(self):
        return bool(self.gamertag)

    @property
    def display(self):  # sourcery skip: remove-unnecessary-else
        base = f"`{self.gamertag}`" if self.gamertag else f"User with XUID {self.xuid}"

        if self.in_game:
            return base
        else:
            time_format = naff.Timestamp.fromdatetime(self.last_seen).format("f")
            return f"{base}: last seen {time_format}"


class GamertagOnCooldown(Exception):
    # used by GamertagHandler to know when to switch to the backup
    def __init__(self) -> None:
        # i could make this anything since this should never be exposed
        # to the user, but who knows
        super().__init__("The gamertag handler is on cooldown!")


class GamertagServiceDown(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The gamertag service is down! The bot is unavailable at this time."
        )


class ClubOnCooldown(Exception):
    def __init__(self) -> None:
        super().__init__("The club handler is on cooldown!")


@attr.s(slots=True)
class GamertagHandler:
    """A special class made to handle the complexities of getting gamertags
    from XUIDs."""

    bot: utils.RealmBotBase = attr.ib()
    sem: asyncio.Semaphore = attr.ib()
    xuids_to_get: typing.Tuple[str, ...] = attr.ib()
    profile: "providers.ProfileProvider" = attr.ib()
    openxbl_session: aiohttp.ClientSession = attr.ib()

    index: int = attr.ib(init=False, default=0)
    responses: typing.List["ProfileResponse"] = attr.ib(init=False, factory=list)
    AMOUNT_TO_GET: int = attr.ib(init=False, default=30)

    async def get_gamertags(self, xuid_list: typing.List[str]) -> None:
        # honestly, i forget what this output can look like by now -
        # but if i remember, it's kinda weird
        profile_resp = await self.profile.get_profiles(xuid_list)
        profile_json = await profile_resp.json(loads=orjson.loads)

        if profile_json.get("code"):  # usually means ratelimited or invalid xuid
            description: str = profile_json["description"]

            if description.startswith("Throttled"):  # ratelimited
                raise GamertagOnCooldown()

            # otherwise, invalid xuid
            desc_split = description.split(" ")
            xuid_list.remove(desc_split[1])

            await self.get_gamertags(
                xuid_list
            )  # after removing, try getting data again

        elif profile_json.get("limitType"):  # ratelimit
            raise GamertagOnCooldown()

        self.responses.append(ProfileResponse.parse_obj(profile_json))
        self.index += self.AMOUNT_TO_GET

    async def backup_get_gamertags(self):
        # openxbl is used throughout this, and its basically a way of navigating
        # the xbox live api in a more sane way than its actually laid out
        # while xbox-webapi-python can also do this without using a 3rd party service,
        # using openxbl can be more reliable at times as it has a generous 500 requests
        # per hour limit on the free tier and is not subject to ratelimits
        # however, there's no bulk xuid > gamertag option, and is a bit slow in general

        for xuid in self.xuids_to_get[self.index :]:
            async with self.openxbl_session.get(
                f"https://xbl.io/api/v2/account/{xuid}"
            ) as r:
                try:
                    resp_json = await r.json(loads=orjson.loads)
                    if "code" in resp_json.keys():  # service is down
                        await utils.msg_to_owner(self.bot, resp_json)
                        raise GamertagServiceDown()
                    else:
                        with contextlib.suppress(ValidationError):
                            self.responses.append(ProfileResponse.parse_obj(resp_json))
                except aiohttp.ContentTypeError:
                    # can happen, if not rare
                    text = await r.text()
                    await utils.msg_to_owner(
                        self.bot,
                        f"Failed to get gamertag of user `{xuid}`.\nResponse code:"
                        f" {r.status}\nText: {text}",
                    )

            self.index += 1

    async def run(self):
        while self.index < len(self.xuids_to_get):
            current_xuid_list = list(self.xuids_to_get[self.index : self.index + 30])

            async with self.sem:
                with contextlib.suppress(GamertagOnCooldown):
                    await self.get_gamertags(current_xuid_list)
                # alright, so we either got 30 gamertags or are ratelimited
                # so now we switch to the backup getter so that we don't have
                # to wait on the ratelimit to request for more gamertags
                # this wait_for basically a little 'exploit` to only make the backup
                # run for 15 seconds or until completetion, whatever comes first
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self.backup_get_gamertags(), timeout=15)
        dict_gamertags: typing.Dict[str, str] = {}

        for profiles in self.responses:
            for user in profiles.profile_users:
                try:
                    # really funny but efficient way of getting gamertag
                    # from this data
                    gamertag = next(
                        s.value for s in user.settings if s.id == "Gamertag"
                    )
                    await self.bot.redis.setex(
                        name=str(user.id),
                        time=datetime.timedelta(days=14),
                        value=gamertag,
                    )
                    dict_gamertags[user.id] = gamertag
                except (KeyError, StopIteration):
                    continue

        return dict_gamertags


async def can_run_playerlist(ctx: utils.RealmContext) -> typing.Any:
    # simple check to see if a person can run the playerlist command
    try:
        guild_config = await ctx.fetch_config()
    except DoesNotExist:
        return False
    return bool(guild_config.club_id)


class Playerlist(utils.Extension):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.sem = asyncio.Semaphore(
            3
        )  # prevents bot from overloading xbox api, hopefully
        self.club_sem = asyncio.Semaphore(10)

        self._previous_now = datetime.datetime.now(tz=datetime.timezone.utc)
        self._online_cache: defaultdict[int, set[str]] = defaultdict(set)
        self._guildplayer_queue: asyncio.Queue[
            list[models.GuildPlayer]
        ] = asyncio.Queue()

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
            await utils.error_handle(self.bot, e)
            return

        player_objs: list[models.GuildPlayer] = []
        gotten_realm_ids: set[int] = set()
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        for realm in realms.servers:
            guild_ids: set[str] = await self.bot.redis.smembers(f"realm-id-{realm.id}")
            if not guild_ids:
                continue

            gotten_realm_ids.add(realm.id)
            player_set: set[str] = set()

            for player in realm.players:
                player_set.add(player.uuid)
                player_objs.extend(
                    models.GuildPlayer(
                        guild_xuid_id=f"{guild_id}-{player.uuid}",
                        online=True,
                        last_seen=now,
                    )
                    for guild_id in guild_ids
                )

            left = self._online_cache[realm.id].difference(player_set)
            self._online_cache[realm.id] = player_set

            for guild_id in guild_ids:
                player_objs.extend(
                    models.GuildPlayer(
                        guild_xuid_id=f"{guild_id}-{player}",
                        online=False,
                        last_seen=self._previous_now,
                    )
                    for player in left
                )

        online_cache_ids = set(self._online_cache.keys())
        for missed_realm_id in online_cache_ids.difference(gotten_realm_ids):
            now_invalid = self._online_cache[missed_realm_id]
            guild_ids: set[str] = await self.bot.redis.smembers(
                f"realm-id-{missed_realm_id}"
            )
            if not now_invalid or not guild_ids:
                continue

            for guild_id in guild_ids:
                player_objs.extend(
                    models.GuildPlayer(
                        guild_xuid_id=f"{guild_id}-{player}",
                        online=False,
                        last_seen=self._previous_now,
                    )
                    for player in now_invalid
                )

            self._online_cache[missed_realm_id] = set()

        self._previous_now = now

        # handle this in the "background" so we don't have to worry about this
        # taking too long
        await self._guildplayer_queue.put(player_objs)

    async def _upload_players(self):
        while True:
            try:
                guildplayers = await self._guildplayer_queue.get()

                await models.GuildPlayer.bulk_create(
                    guildplayers,
                    on_conflict=("guild_xuid_id",),
                    update_fields=("online", "last_seen"),
                )
            except Exception as e:
                if isinstance(e, asyncio.CancelledError):
                    return
                await utils.error_handle(self.bot, e)
            finally:
                if not self._guildplayer_queue.empty():
                    self._guildplayer_queue.task_done()

    async def _delete_after(self, msg: naff.Message):
        await asyncio.sleep(3)
        with contextlib.suppress(naff.errors.HTTPException):
            await msg.delete()

    async def get_players_from_guildplayers(
        self,
        guild_id: str,
        guildplayers: list[models.GuildPlayer],
    ):
        player_list: typing.List[Player] = []
        unresolved_dict: typing.Dict[str, Player] = {}

        for member in guildplayers:
            xuid = member.guild_xuid_id.removeprefix(f"{guild_id}-")

            player = Player(
                xuid,
                member.last_seen,
                member.online,
                await self.bot.redis.get(xuid),
            )
            if player.resolved:
                player_list.append(player)
            else:
                unresolved_dict[xuid] = player

        if unresolved_dict:
            gamertag_handler = GamertagHandler(
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
    @naff.check(can_run_playerlist)  # type: ignore
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

        actual_hours_ago: int = int(hours_ago)

        now = naff.Timestamp.utcnow()

        time_delta = datetime.timedelta(hours=actual_hours_ago)
        time_ago = now - time_delta

        guildplayers = await models.GuildPlayer.filter(
            Q(guild_xuid_id__startswith=f"{ctx.guild_id}-"),
            Q(Q(online=True), Q(last_seen__gte=time_ago), join_type="OR"),
        )

        if not guildplayers:
            if not kwargs.get("no_init_mes"):
                raise utils.CustomCheckFailure(
                    "No one seems to have been on the Realm for the last "
                    + f"{actual_hours_ago} hour(s). If you changed Realms, make sure to"
                    " let the owner know. Make sure you also haven't accidentally"
                    " banned the bot's Xbox account.\n\nIf you just invited the bot,"
                    " this will take a while to populate - after a day or two, it'll"
                    " be fully ready."
                )
            else:
                return

        player_list = await self.get_players_from_guildplayers(
            str(ctx.guild_id), guildplayers
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
            # gets the offline list in lines of 40
            # basically, it's like
            # [ [list of 40 strings] [list of 40 strings] etc.]
            chunks = [offline_list[x : x + 40] for x in range(0, len(offline_list), 40)]

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

        if not kwargs.get("no_init_mes") and not online_list and not offline_list:
            raise utils.CustomCheckFailure(
                "No one has been on the Realm for the last "
                + f"{actual_hours_ago} hour(s)."
            )

    @naff.slash_command("online", description="Allows you to see if anyone is online on the Realm right now.", dm_permission=False)  # type: ignore
    @naff.cooldown(naff.Buckets.GUILD, 1, 10)
    @naff.check(can_run_playerlist)  # type: ignore
    async def online(self, ctx: utils.RealmContext):
        """Allows you to see if anyone is online on the Realm right now."""
        # uses much of the same code as playerlist

        guildplayers = await models.GuildPlayer.filter(
            guild_xuid_id__startswith=f"{ctx.guild_id}-", online=True
        )
        player_list = await self.get_players_from_guildplayers(
            str(ctx.guild_id), guildplayers
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
    Playerlist(bot)
