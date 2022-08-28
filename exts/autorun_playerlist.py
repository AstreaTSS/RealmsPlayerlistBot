import asyncio
import contextlib
import datetime
import importlib
import typing

import naff
from dateutil.relativedelta import relativedelta

import common.classes as cclasses
import common.models as models
import common.utils as utils


class AutoRunPlayerlist(utils.Extension):
    # the cog that controls the automatic version of the playerlist
    # this way, we can fix the main playerlist command itself without
    # resetting the autorun cycle

    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.playerlist_task = asyncio.create_task(self._start_playerlist())
        self.playerlist_realms_delete.start()

    def drop(self):
        self.playerlist_task.cancel()
        self.playerlist_realms_delete.stop()
        super().drop()

    async def _eventually_invalidate(self, guild_config: models.GuildConfig):
        # the idea here is to invalidate autorunners that simply can't be run
        # there's a bit of generousity here, as the code gives a total of 3 hours
        # before actually doing it
        num_times = await self.bot.redis.incr(
            f"invalid-playerlist-{guild_config.guild_id}"
        )

        if num_times > 3:
            guild_config.playerlist_chan = None
            await guild_config.save()
            await self.bot.redis.delete(f"invalid-playerlist-{guild_config.guild_id}")

    async def _start_playerlist(self):
        await self.bot.fully_ready.wait()

        try:
            while True:
                premium_run = False

                # margin of error
                now = naff.Timestamp.utcnow() + datetime.timedelta(milliseconds=1)
                if now.minute >= 30:
                    next_delta = relativedelta(
                        hours=+1, minute=0, second=0, microsecond=0
                    )
                else:
                    premium_run = True
                    next_delta = relativedelta(minute=30, second=0, microsecond=0)
                next_time = now + next_delta

                await utils.sleep_until(next_time)
                await self.playerlist_loop(premium_run)
        except Exception as e:
            if not isinstance(e, asyncio.CancelledError):
                await utils.error_handle(self.bot, e)

    @naff.Task.create(naff.IntervalTrigger(hours=6))
    async def playerlist_realms_delete(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        time_back = now - datetime.timedelta(hours=25)
        await models.RealmPlayer.filter(
            online=False,
            last_seen__lt=time_back,
        ).delete()

    async def playerlist_loop(self, premium_run: bool):
        """
        A simple way of running the playerlist command every hour in every server the bot is in.
        """

        list_cmd = next(
            c for c in self.bot.application_commands if c.name.default == "playerlist"
        )
        to_run = []

        kwargs: dict[typing.Any, typing.Any] = {
            "guild_id__in": list(self.bot.user._guild_ids)
        }

        if premium_run:
            kwargs["premium_code__id__not_isnull"] = True

        async for guild_config in models.GuildConfig.filter(**kwargs).prefetch_related(
            "premium_code"
        ):
            if (
                guild_config.club_id
                and guild_config.realm_id
                and guild_config.playerlist_chan
            ):
                to_run.append(
                    self.auto_run_playerlist(list_cmd, guild_config, premium_run)
                )

        # this gather is done so that they can all run in parallel
        # should make things slightly faster for everyone
        output = await asyncio.gather(*to_run, return_exceptions=True)

        # all of this to send errors to the bot owner/me without
        # stopping this entirely
        for message in output:
            if isinstance(message, Exception):
                await utils.error_handle(self.bot, message)

    def error_handle(self, error: Exception):
        asyncio.create_task(utils.error_handle(self.bot, error))

    async def auto_run_playerlist(
        self,
        list_cmd: naff.InteractionCommand,
        guild_config: models.GuildConfig,
        premium_run: bool,
    ):
        try:
            chan = await self.bot.cache.fetch_channel(guild_config.playerlist_chan)  # type: ignore
        except naff.errors.HTTPException:
            await self._eventually_invalidate(guild_config)
            return

        if not isinstance(chan, naff.GuildText):
            return

        try:
            chan = cclasses.valid_channel_check(chan)
        except naff.errors.BadArgument:
            with contextlib.suppress(naff.errors.HTTPException):
                await chan.send(
                    "I could not view message history for this channel when"
                    " automatically running the playerlist. This is needed in order to"
                    " run it automatically. Please make sure the bot has the ability to"
                    " read message history for this channel."
                )

            await self._eventually_invalidate(guild_config)
            return

        # make a fake context to make things easier
        a_ctx: utils.RealmPrefixedContext = utils.RealmPrefixedContext(
            client=self.bot,  # type: ignore
            author=chan.guild.me,
            channel=chan,
            guild_id=chan._guild_id,
            guild_config=guild_config,
        )

        # take advantage of the fact that users cant really use kwargs for commands
        # the two listed here silence the 'this may take a long time' message
        # and also make it so it doesnt go back 12 hours, instead only going two

        if premium_run:
            await list_cmd.callback(a_ctx, "1", no_init_mes=True)
        else:
            await list_cmd.callback(a_ctx, "2", no_init_mes=True)


def setup(bot):
    importlib.reload(utils)
    importlib.reload(cclasses)
    AutoRunPlayerlist(bot)
