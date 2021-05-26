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
        document_url = os.environ.get("CONFIG_URL")

        async with aiohttp.ClientSession() as session:
            async with session.get(document_url) as resp:
                self.bot.config = await resp.json(content_type="text/plain")

    @fetch_document.error
    async def error_handle(self, *args):
        error = args[-1]
        await utils.error_handle(self.bot, error)


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(FetchConfigFile(bot))
