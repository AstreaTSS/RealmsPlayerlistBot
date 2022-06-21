import asyncio
import datetime
import importlib
import math
import typing
from collections import defaultdict

import naff

import common.models as models
import common.playerlist_utils as pl_utils
import common.utils as utils


class Online(utils.Extension):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.sem = asyncio.Semaphore(
            3
        )  # prevents bot from overloading xbox api, hopefully

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

    async def get_players_from_guildplayers(
        self,
        guild_id: str,
        guildplayers: list[models.GuildPlayer],
    ):
        player_list: typing.List[pl_utils.Player] = []
        unresolved_dict: typing.Dict[str, pl_utils.Player] = {}

        for member in guildplayers:
            xuid = member.guild_xuid_id.removeprefix(f"{guild_id}-")

            player = pl_utils.Player(
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

    @naff.slash_command("online", description="Allows you to see if anyone is online on the Realm right now.", dm_permission=False)  # type: ignore
    @naff.cooldown(naff.Buckets.GUILD, 1, 10)
    @naff.check(pl_utils.can_run_playerlist)  # type: ignore
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
    importlib.reload(pl_utils)
    Online(bot)
