"""
Copyright 2020-2024 AstreaTSS.
This file is part of the Realms Playerlist Bot.

The Realms Playerlist Bot is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

The Realms Playerlist Bot is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with the Realms
Playerlist Bot. If not, see <https://www.gnu.org/licenses/>.
"""

import asyncio
import contextlib
import datetime
import importlib

import interactions as ipy

import common.classes as cclasses
import common.models as models
import common.playerlist_events as pl_events
import common.playerlist_utils as pl_utils
import common.utils as utils

UPSELLS = [
    (
        "Want minute-to-minute updates on your Realm? Do you want device information"
        " for players? Check out Playerlist Premium: /premium info"
    ),
    (
        "If you like the bot, you can vote for it via /vote! Voting helps the bot grow"
        " and get more features."
    ),
    (
        "Do you want a constantly updating live online list? Check out Playerlist"
        " Premium: /premium info"
    ),
    "Check out all of the features the bot has: https://rpl.astrea.cc/wiki/features",
    (
        "Having issues with the bot? Check out the FAQ or join the support server:"
        " /support"
    ),
]
LENGTH_UPSELLS = len(UPSELLS)


def upsell_determiner(dt: datetime.datetime) -> str | None:
    if dt.hour % 6 == 0:
        total_seconds = int(dt.timestamp())
        x_hour_boundary = total_seconds % (21600 * LENGTH_UPSELLS)
        return UPSELLS[x_hour_boundary // 21600]

    return None


def period_determiner(period_index: int) -> int:
    match period_index:
        case 1:
            return 1
        case 2:
            return 7
        case 3:
            return 14
        case 4:
            return 30

    raise ValueError("This should never happen.")


class Autorunners(utils.Extension):
    # the cog that controls the automatic version of the some commands
    # this way, we can fix the main command itself without
    # resetting the autorun cycle

    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.playerlist_task = self.bot.create_task(self._start_playerlist())
        self.reoccurring_lb_task.start()
        self.player_session_delete.start()

    def drop(self) -> None:
        self.playerlist_task.cancel()
        self.reoccurring_lb_task.stop()
        self.player_session_delete.stop()
        super().drop()

    async def _start_playerlist(self) -> None:
        await self.bot.fully_ready.wait()

        while True:
            try:
                # margin of error
                now = ipy.Timestamp.utcnow() + datetime.timedelta(milliseconds=1)
                next_time = now.replace(minute=59, second=59, microsecond=0)

                # yes, next_time could be in the past, but that's handled by sleep_until
                await utils.sleep_until(next_time)

                # wait for the playerlist to finish parsing
                with contextlib.suppress(asyncio.TimeoutError):
                    await self.bot.wait_for(pl_events.PlayerlistParseFinish, timeout=15)

                await self.playerlist_loop(upsell=upsell_determiner(next_time))
            except Exception as e:
                if not isinstance(e, asyncio.CancelledError):
                    await utils.error_handle(e)
                else:
                    return

    async def playerlist_loop(
        self,
        upsell: str | None,
    ) -> None:
        """
        A simple way of running the playerlist command every hour in every server the bot is in.
        """

        list_cmd = next(
            c for c in self.bot.application_commands if str(c.name) == "playerlist"
        )

        configs = await models.AutorunGuildConfig.prisma().find_many(
            where={
                "guild_id": {"in": [int(g) for g in self.bot.user._guild_ids]},
                "live_playerlist": False,
                "NOT": [{"realm_id": None}, {"playerlist_chan": None}],
            },
            include={"premium_code": True},
        )

        realm_ids = {c.realm_id for c in configs}
        for config in configs:
            if config.fetch_devices and config.valid_premium:
                realm_ids.discard(config.realm_id)

        now = ipy.Timestamp.utcnow().replace(second=30)
        time_delta = datetime.timedelta(hours=1, minutes=5)
        time_ago = now - time_delta

        player_sessions = await models.AutorunPlayerSession.prisma().find_many(
            distinct=["xuid"],
            order=[{"xuid": "asc"}, {"last_seen": "desc"}],
            where={
                "realm_id": {"in": list(realm_ids)},
                "OR": [{"online": True}, {"last_seen": {"gte": time_ago}}],
            },
        )

        gamertag_map = await pl_utils.get_xuid_to_gamertag_map(
            self.bot, [p.xuid for p in player_sessions]
        )

        to_run = [
            self.auto_run_playerlist(list_cmd, config, upsell, gamertag_map)
            for config in configs
        ]

        # why not use a taskgroup? because if we did, if one task errored,
        # the entire thing would stop and we don't want that
        output = await asyncio.gather(*to_run, return_exceptions=True)
        for message in output:
            if isinstance(message, Exception):
                await utils.error_handle(message)

    async def auto_run_playerlist(
        self,
        list_cmd: ipy.InteractionCommand,
        config: models.AutorunGuildConfig,
        upsell: str | None,
        gamertag_map: dict[str, str],
    ) -> None:
        if config.guild_id in self.bot.unavailable_guilds:
            return

        # make a fake context to make things easier
        a_ctx = utils.RealmPrefixedContext(client=self.bot)
        a_ctx.author_id = self.bot.user.id
        a_ctx.channel_id = ipy.to_snowflake(config.playerlist_chan)
        a_ctx.guild_id = ipy.to_snowflake(config.guild_id)
        a_ctx.config = config  # type: ignore

        a_ctx.prefix = ""
        a_ctx.content_parameters = ""
        a_ctx.command = None  # type: ignore
        a_ctx.args = []
        a_ctx.kwargs = {}

        # take advantage of the fact that users cant really use kwargs for commands
        # the ones listed here silence the 'this may take a long time' message
        # and also make it so it doesnt go back 12 hours, instead only going one
        # and yes, add the upsell info

        try:
            await asyncio.wait_for(
                list_cmd.callback(
                    a_ctx,
                    1,
                    autorunner=True,
                    upsell=upsell,
                    gamertag_map=gamertag_map,
                ),
                timeout=60,
            )
        except ipy.errors.HTTPException as e:
            if e.status < 500:
                # likely a can't send in channel, eventually invalidate and move on
                full_config = await models.GuildConfig.prisma().find_unique(
                    where={"guild_id": config.guild_id}
                )
                if not full_config:
                    return

                await pl_utils.eventually_invalidate(self.bot, full_config)

    @ipy.Task.create(ipy.CronTrigger("0 0 * * 0"))
    async def reoccurring_lb_task(self) -> None:
        # margin of error
        now = ipy.Timestamp.utcnow() + datetime.timedelta(milliseconds=1)

        # silly way to have a bitfield that toggles every sunday
        bit = self.bot.redis.bitfield("rpl-sunday-bitshift", default_overflow="WRAP")
        bit.incrby("u1", "#0", 1)
        bit_resp: list[int] = await bit.execute()  # [0] or [1]

        await self.reoccurring_lb_loop(bit_resp[0] % 2 == 0, now.day <= 7)

    async def reoccurring_lb_loop(
        self, second_sunday: bool, first_monday_of_month: bool
    ) -> None:
        lb_command = next(
            c for c in self.bot.application_commands if str(c.name) == "leaderboard"
        )

        if second_sunday and first_monday_of_month:
            configs = await models.GuildConfig.prisma().find_many(
                where={
                    "guild_id": {"in": [int(g) for g in self.bot.user._guild_ids]},
                    "NOT": [{"realm_id": None}, {"reoccurring_leaderboard": None}],
                },
                include={"premium_code": True},
            )
        elif first_monday_of_month:
            configs = await models.GuildConfig.prisma().find_many(
                where={
                    "guild_id": {"in": [int(g) for g in self.bot.user._guild_ids]},
                    "NOT": [
                        {"realm_id": None},
                        {"reoccurring_leaderboard": {"gte": 20, "lt": 30}},
                    ],
                },
                include={"premium_code": True},
            )
        elif second_sunday:
            configs = await models.GuildConfig.prisma().find_many(
                where={
                    "guild_id": {"in": [int(g) for g in self.bot.user._guild_ids]},
                    "NOT": [
                        {"realm_id": None},
                        {"reoccurring_leaderboard": {"gte": 30, "lt": 40}},
                    ],
                },
                include={"premium_code": True},
            )
        else:
            configs = await models.GuildConfig.prisma().find_many(
                where={
                    "guild_id": {"in": [int(g) for g in self.bot.user._guild_ids]},
                    "NOT": [
                        {"realm_id": None},
                        {"reoccurring_leaderboard": {"gte": 20}},
                    ],
                },
                include={"premium_code": True},
            )

        to_run = [self.send_reoccurring_lb(lb_command, config) for config in configs]
        output = await asyncio.gather(*to_run, return_exceptions=True)

        for message in output:
            if isinstance(message, Exception):
                await utils.error_handle(message)

    async def send_reoccurring_lb(
        self,
        lb_command: ipy.InteractionCommand,
        config: models.GuildConfig,
    ) -> None:
        if config.guild_id in self.bot.unavailable_guilds:
            return

        if not config.valid_premium:
            await pl_utils.invalidate_premium(self.bot, config)
            return

        # make a fake context to make things easier
        a_ctx = utils.RealmPrefixedContext(client=self.bot)
        a_ctx.author_id = self.bot.user.id
        a_ctx.channel_id = ipy.to_snowflake(
            config.notification_channels.get(
                "reoccurring_leaderboard", config.playerlist_chan
            )  # type: ignore
        )
        a_ctx.guild_id = ipy.to_snowflake(config.guild_id)
        a_ctx.config = config

        a_ctx.prefix = ""
        a_ctx.content_parameters = ""
        a_ctx.command = None
        a_ctx.args = []
        a_ctx.kwargs = {}

        try:
            await asyncio.wait_for(
                lb_command.callback(
                    a_ctx,
                    period_determiner(config.reoccurring_leaderboard % 10),
                    autorunner=True,
                ),
                timeout=180,
            )
        except ipy.errors.BadArgument:
            return
        except ipy.errors.HTTPException as e:
            if e.status < 500:
                if config.notification_channels.get("reoccurring_leaderboard"):
                    await pl_utils.eventually_invalidate_reoccurring_lb(
                        self.bot, config
                    )
                else:
                    await pl_utils.eventually_invalidate(self.bot, config)

    @ipy.Task.create(ipy.CronTrigger("0 0,12 * * *"))
    async def player_session_delete(self) -> None:
        now = datetime.datetime.now(tz=datetime.UTC)
        time_back = now - datetime.timedelta(days=31)
        await models.PlayerSession.prisma().delete_many(
            where={"online": False, "last_seen": {"lt": time_back}}
        )


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(pl_utils)
    importlib.reload(cclasses)
    Autorunners(bot)
