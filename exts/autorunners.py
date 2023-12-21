"""
Copyright 2020-2023 AstreaTSS.
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
import datetime
import importlib

import interactions as ipy
from dateutil.relativedelta import relativedelta

import common.classes as cclasses
import common.models as models
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
    (
        "If you like the bot, you can vote for it via /vote! Voting helps the bot grow"
        " and get more features."
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
        self.reoccuring_lb_task = self.bot.create_task(self._start_reoccurring_lb())
        self.player_session_delete.start()

    def drop(self) -> None:
        self.playerlist_task.cancel()
        self.reoccuring_lb_task.cancel()
        self.player_session_delete.stop()
        super().drop()

    async def _start_playerlist(self) -> None:
        await self.bot.fully_ready.wait()

        try:
            while True:
                # margin of error
                now = ipy.Timestamp.utcnow() + datetime.timedelta(milliseconds=1)
                next_delta = relativedelta(hours=+1, minute=0, second=5, microsecond=0)
                next_time = now + next_delta

                await utils.sleep_until(next_time)

                await self.playerlist_loop(upsell=upsell_determiner(next_time))
        except Exception as e:
            if not isinstance(e, asyncio.CancelledError):
                await utils.error_handle(e)

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

        to_run = [
            self.auto_run_playerlist(list_cmd, config, upsell)
            for config in await models.GuildConfig.prisma().find_many(
                where={
                    "guild_id": {"in": [int(g) for g in self.bot.user._guild_ids]},
                    "live_playerlist": False,
                    "NOT": [{"realm_id": None}, {"playerlist_chan": None}],
                },
                include={"premium_code": True},
            )
        ]
        # this gather is done so that they can all run in parallel
        # should make things slightly faster for everyone
        output = await asyncio.gather(*to_run, return_exceptions=True)

        # all of this to send errors without stopping this entirely
        for message in output:
            if isinstance(message, Exception):
                await utils.error_handle(message)

    async def auto_run_playerlist(
        self,
        list_cmd: ipy.InteractionCommand,
        config: models.GuildConfig,
        upsell: str | None,
    ) -> None:
        if config.guild_id in self.bot.unavailable_guilds:
            return

        # make a fake context to make things easier
        a_ctx = utils.RealmPrefixedContext(client=self.bot)
        a_ctx.author_id = self.bot.user.id
        a_ctx.channel_id = ipy.to_snowflake(config.playerlist_chan)
        a_ctx.guild_id = ipy.to_snowflake(config.guild_id)
        a_ctx.config = config

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
            await list_cmd.callback(
                a_ctx,
                1,
                autorunner=True,
                upsell=upsell,
            )
        except ipy.errors.HTTPException as e:
            if e.status < 500:
                # likely a can't send in channel, eventually invalidate and move on
                await pl_utils.eventually_invalidate(self.bot, config)

    async def _start_reoccurring_lb(self) -> None:
        await self.bot.fully_ready.wait()
        try:
            while True:
                # margin of error
                now = ipy.Timestamp.utcnow() + datetime.timedelta(milliseconds=1)

                days_to_next_sunday = 6 - now.weekday()
                if days_to_next_sunday <= 0:
                    days_to_next_sunday += 7

                next_sunday = now + relativedelta(
                    days=+days_to_next_sunday, hour=0, minute=0, second=0, microsecond=0
                )

                # silly way to have a bitfield that toggles every sunday
                bit = self.bot.redis.bitfield(
                    "rpl-sunday-bitshift", default_overflow="WRAP"
                )
                bit.incrby("u1", "#0", 1)
                bit_resp: list[int] = await bit.execute()  # [0] or [1]

                await utils.sleep_until(next_sunday)
                await self.reoccurring_lb_loop(
                    bit_resp[0] % 2 == 0, next_sunday.day <= 7
                )

        except Exception as e:
            if not isinstance(e, asyncio.CancelledError):
                await utils.error_handle(e)

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
            await lb_command.callback(
                a_ctx, period_determiner(config.reoccurring_leaderboard % 10)
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

    @ipy.Task.create(
        ipy.OrTrigger(ipy.TimeTrigger(utc=True), ipy.TimeTrigger(hour=12, utc=True))
    )
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
