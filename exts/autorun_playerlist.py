import asyncio
import contextlib
import datetime
import importlib

import naff
from dateutil.relativedelta import relativedelta

import common.models as models
import common.utils as utils


class BetterIntervalTrigger(naff.IntervalTrigger):
    def __new__(cls, *args, **kwargs) -> naff.BaseTrigger:
        new_cls = super().__new__(cls)
        new_cls.last_call_time = datetime.datetime.now() - datetime.timedelta(
            hours=1, seconds=1
        )
        return new_cls


class AutoRunPlayerlist(utils.Extension):
    # the cog that controls the automatic version of the playerlist
    # this way, we can fix the main playerlist command itself without
    # resetting the autorun cycle

    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.playerlist_task = asyncio.create_task(self._start_playerlist())
        self.playerlist_delete.start()

    def drop(self):
        self.playerlist_task.cancel()
        self.playerlist_delete.stop()
        super().drop()

    async def _start_playerlist(self):
        await self.bot.fully_ready.wait()

        try:
            while True:
                # margin of error
                now = naff.Timestamp.utcnow() + datetime.timedelta(milliseconds=1)
                next_delta = relativedelta(hours=+1, minute=0, second=0, microsecond=0)
                next_time = now + next_delta

                await utils.sleep_until(next_time)
                await self.playerlist_loop()
        except Exception as e:
            if not isinstance(e, asyncio.CancelledError):
                await utils.error_handle(self.bot, e)

    @naff.Task.create(naff.IntervalTrigger(hours=6))
    async def playerlist_delete(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        very_long_back = now - datetime.timedelta(hours=25)
        await models.GuildPlayer.filter(
            online=False, last_seen__lt=very_long_back
        ).delete()

    async def playerlist_loop(self):
        """A simple way of running the playerlist command every hour in every server the bot is in."""

        list_cmd = next(
            c for c in self.bot.application_commands if c.name.default == "playerlist"
        )
        to_run = []

        async for guild_config in models.GuildConfig.all():
            if bool(guild_config.club_id):
                to_run.append(self.auto_run_playerlist(list_cmd, guild_config))

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
        self, list_cmd: naff.InteractionCommand, guild_config: models.GuildConfig
    ):
        chan: naff.GuildText = self.bot.get_channel(
            guild_config.playerlist_chan  # type: ignore
        )  # type: ignore # playerlist channel

        # gets the most recent message in the playerlist channel
        try:
            messages = await chan.history(limit=1).flatten()
        except naff.errors.HTTPException:
            with contextlib.suppress(naff.errors.HTTPException):
                await chan.send(
                    "I could not view message history for this channel when"
                    " automatically running the playerlist. This is needed in order to"
                    " run it automatically. Please make sure the bot has the ability to"
                    " read message history for this channel."
                )
            await utils.msg_to_owner(self.bot, f"{chan.guild}")
            return

        a_ctx: utils.RealmPrefixedContext = await self.bot.get_context(messages[0])  # type: ignore
        a_ctx.guild_config = guild_config  # to speed things up

        # take advantage of the fact that users cant really use kwargs for commands
        # the two listed here silence the 'this may take a long time' message
        # and also make it so it doesnt go back 12 hours, instead only going two
        await list_cmd.callback(a_ctx, "2", no_init_mes=True)


def setup(bot):
    importlib.reload(utils)
    AutoRunPlayerlist(bot)
