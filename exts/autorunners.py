"""
Copyright 2020-2025 AstreaTSS.
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
from pypika import Order, PostgreSQLQuery, Table
from tortoise.expressions import Q

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
        "Check out all of the features the bot has:"
        " https://playerlist.astrea.cc/wiki/features"
    ),
    (
        "Do you want a constantly updating live online list? Check out Playerlist"
        " Premium: /premium info"
    ),
    (
        "Having issues with the bot? Check out the FAQ or join the support server:"
        " /support"
    ),
]

if utils.VOTING_ENABLED:
    UPSELLS.append(
        "If you like the bot, you can vote for it via /vote! Voting helps the bot grow"
        " and get more features."
    )

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

        configs = await models.GuildConfig.filter(
            guild_id__in=[int(g) for g in self.bot.user._guild_ids],
            live_playerlist=False,
            realm_id__isnull=False,
            playerlist_chan__isnull=False,
        ).prefetch_related("premium_code")
        if not configs:
            return

        realm_ids = {c.realm_id for c in configs}
        for config in configs:
            if config.fetch_devices and config.valid_premium:
                realm_ids.discard(config.realm_id)

        now = ipy.Timestamp.utcnow().replace(second=30)
        time_delta = datetime.timedelta(hours=1, minutes=5)
        time_ago = now - time_delta

        playersession = Table(models.PlayerSession.Meta.table)
        query = (
            PostgreSQLQuery.from_(playersession)
            .select(*models.PlayerSession._meta.fields)
            .where(
                playersession.realm_id.isin(list(realm_ids))
                & (
                    playersession.online.eq(True)
                    | playersession.last_seen.gte(time_ago)
                )
            )
            .orderby("xuid", order=Order.asc)
            .orderby("last_seen", order=Order.desc)
            .distinct_on("xuid")  # type: ignore
        )

        player_sessions: list[models.PlayerSession] = await models.PlayerSession.raw(
            str(query)
        )  # type: ignore
        if not player_sessions:
            return

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
        config: models.GuildConfig,
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
                await pl_utils.eventually_invalidate(self.bot, config)

    async def _start_reoccurring_lb(self) -> None:
        await self.bot.fully_ready.wait()
        try:
            while True:
                # margin of error
                now = ipy.Timestamp.utcnow() + datetime.timedelta(milliseconds=1)

                tomorrow = now.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) + datetime.timedelta(days=1)

                if tomorrow.weekday() == 6:
                    # silly way to have a bitfield that toggles every sunday
                    bit = self.bot.valkey.bitfield(
                        "rpl-sunday-bitshift", default_overflow="WRAP"
                    )
                    bit.incrby("u1", "#0", 1)
                    bit_resp: list[int] = await bit.execute()  # [0] or [1]
                else:
                    bit_resp: list[int] = [1]

                await utils.sleep_until(tomorrow)
                await self.reoccurring_lb_loop(
                    tomorrow.weekday() == 6, bit_resp[0] % 2 == 0, tomorrow.day <= 7
                )

        except Exception as e:
            if not isinstance(e, asyncio.CancelledError):
                await utils.error_handle(e)

    async def reoccurring_lb_loop(
        self, sunday: bool, second_sunday: bool, first_sunday_of_month: bool
    ) -> None:
        lb_command = next(
            c for c in self.bot.application_commands if str(c.name) == "leaderboard"
        )

        if not sunday:
            configs = await models.GuildConfig.filter(
                guild_id__in=[int(g) for g in self.bot.user._guild_ids],
                reoccurring_leaderboard__isnull=False,
                realm_id__isnull=False,
                reoccurring_leaderboard__gte=40,
                reoccurring_leaderboard__lt=50,
            ).prefetch_related("premium_code")
        elif second_sunday and first_sunday_of_month:
            configs = await models.GuildConfig.filter(
                guild_id__in=[int(g) for g in self.bot.user._guild_ids],
                reoccurring_leaderboard__isnull=False,
                realm_id__isnull=False,
            ).prefetch_related("premium_code")
        elif first_sunday_of_month:
            configs = await models.GuildConfig.filter(
                Q(guild_id__in=[int(g) for g in self.bot.user._guild_ids])
                & Q(reoccurring_leaderboard__isnull=False)
                & Q(realm_id__isnull=False)
                & ~(
                    Q(reoccurring_leaderboard__gte=20)
                    & Q(reoccurring_leaderboard__lt=30)
                )
            ).prefetch_related("premium_code")
        elif second_sunday:
            configs = await models.GuildConfig.filter(
                Q(guild_id__in=[int(g) for g in self.bot.user._guild_ids])
                & Q(reoccurring_leaderboard__isnull=False)
                & Q(realm_id__isnull=False)
                & ~(
                    Q(reoccurring_leaderboard__gte=30)
                    & Q(reoccurring_leaderboard__lt=40)
                )
            ).prefetch_related("premium_code")
        else:
            configs = await models.GuildConfig.filter(
                Q(guild_id__in=[int(g) for g in self.bot.user._guild_ids])
                & Q(reoccurring_leaderboard__isnull=False)
                & Q(realm_id__isnull=False)
                & ~(
                    Q(reoccurring_leaderboard__gte=20)
                    & Q(reoccurring_leaderboard__lt=40)
                )
            ).prefetch_related("premium_code")

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
            config.get_notif_channel("reoccurring_leaderboard")
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

    @ipy.Task.create(
        ipy.OrTrigger(ipy.TimeTrigger(utc=True), ipy.TimeTrigger(hour=12, utc=True))
    )
    async def player_session_delete(self) -> None:
        now = datetime.datetime.now(tz=datetime.UTC)
        time_back = now - datetime.timedelta(days=31)

        await models.PlayerSession.filter(
            online=False,
            last_seen__lt=time_back,
        ).delete()

        too_far_ago = now - datetime.timedelta(hours=1)
        online_for_too_long = await models.PlayerSession.filter(
            online=True, last_seen__lt=too_far_ago
        )

        await models.PlayerSession.filter(
            online=True, last_seen__lt=too_far_ago
        ).update(online=False)

        for session in online_for_too_long:
            self.bot.online_cache[int(session.realm_id)].discard(session.xuid)


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(pl_utils)
    importlib.reload(cclasses)
    Autorunners(bot)
