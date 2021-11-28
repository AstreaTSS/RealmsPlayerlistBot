import importlib
import os

import aiohttp
from discord.ext import commands
from discord.ext import tasks

import common.utils as utils


class FetchConfigFile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fetch_document.start()

    def cog_unload(self):
        self.fetch_document.cancel()

    @tasks.loop(minutes=2.5)
    async def fetch_document(self):
        # this url has to be pointing to the raw text of something that looks like
        # 'config.json'
        # in production this points to the github page of 'config.json'

        # each club looks like this:
        # {
        #   'A-GUILD-ID-AS-A-STRING': {
        #       "season_role": "However their season roles are named, with
        #       'X' being used for whatever changes each season.",
        #
        #       "playerlist_chan": PLAYERLIST-DISCORD-CHANNEL,
        #
        #       "club_id": "XBOX CLUB ID AS A STR",
        #       (you can get it by using the web Xbox app and navigating to the club)
        #       (the id will be in the url)
        #
        #       "announce_chan": ANNOUNCEMENTS-DISCORD-CHANNEL
        #   }
        # }
        document_url = os.environ.get("CONFIG_URL")
        headers = {"Cache-Control": "no-cache", "Pragma": "no-cache"}

        async with aiohttp.ClientSession() as session:
            async with session.get(document_url, headers=headers) as resp:
                self.bot.config = await resp.json(content_type="text/plain")

    @fetch_document.error
    async def error_handle(self, *args):
        error = args[-1]
        await utils.error_handle(self.bot, error)


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(FetchConfigFile(bot))
