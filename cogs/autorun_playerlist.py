import asyncio
import importlib

from nextcord.ext import commands
from nextcord.ext import tasks

import common.utils as utils
from common.models import GuildConfig


class AutoRunPlayerlist(commands.Cog):
    # the cog that controls the automatic version of the playerlist
    # this way, we can fix the main playerlist command itself without
    # resetting the autorun cycle

    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.playerlist_loop.start()

    def cog_unload(self):
        self.playerlist_loop.cancel()

    async def auto_run_playerlist(self, list_cmd, guild_config: GuildConfig):
        chan = self.bot.get_channel(guild_config.playerlist_chan)  # playerlist channel

        # gets the most recent message in the playerlist channel
        # its used to fetch a specific message from there, but honestly, this method is better
        messages = await chan.history(limit=1).flatten()
        a_ctx = await self.bot.get_context(messages[0])

        # little hack so we dont accidentally ping a random person
        a_ctx.reply = a_ctx.send

        # take advantage of the fact that users cant really use kwargs for commands
        # the two listed here silence the 'this may take a long time' message
        # and also make it so it doesnt go back 24 hours, instead only going two
        await a_ctx.invoke(list_cmd, "2", no_init_mes=True)

    @tasks.loop(hours=1)
    async def playerlist_loop(self):
        """A simple way of running the playerlist command every hour in every server the bot is in.
        Or, at least, in every server that's listed in the config. See `config.json` for that.
        See `cogs.config_fetch` for how the bot gets the config from that file."""

        list_cmd = self.bot.get_command("playerlist")
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

    @playerlist_loop.error
    async def error_handle(self, *args):
        error = args[-1]
        await utils.error_handle(self.bot, error)


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(AutoRunPlayerlist(bot))
