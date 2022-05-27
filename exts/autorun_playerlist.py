import asyncio
import contextlib
import datetime
import importlib

import naff

import common.utils as utils
from common.models import GuildConfig


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

        self.playerlist_loop.on_error = self.error_handle
        self.bot.register_task(self.playerlist_loop)

    def drop(self):
        self.bot.cancel_task(self.playerlist_loop)
        super().drop()

    async def auto_run_playerlist(
        self, list_cmd: naff.InteractionCommand, guild_config: GuildConfig
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

    @naff.Task.create(BetterIntervalTrigger(hours=1))
    async def playerlist_loop(self):
        """A simple way of running the playerlist command every hour in every server the bot is in.
        Or, at least, in every server that's listed in the config. See `config.json` for that.
        See `cogs.config_fetch` for how the bot gets the config from that file."""

        list_cmd = next(
            c for c in self.bot.application_commands if c.name.default == "playerlist"
        )
        to_run = []

        async for guild_config in GuildConfig.all():
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


def setup(bot):
    importlib.reload(utils)
    AutoRunPlayerlist(bot)
