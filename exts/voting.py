import importlib
import os

import aiohttp
import naff

import common.utils as utils


class Voting(naff.Extension):
    def __init__(self, bot: utils.RealmBotBase):
        self.bot: utils.RealmBotBase = bot
        self.name = "Voting"

        self.BASE_URL = "https://top.gg/api"
        self.session = aiohttp.ClientSession(
            headers={"Authorization": os.environ["TOP_GG_TOKEN"]}
        )

        self.autopost_guild_count.start()

    def drop(self):
        self.autopost_guild_count.stop()
        super().drop()

    @naff.Task.create(naff.IntervalTrigger(minutes=30))
    async def autopost_guild_count(self):
        server_count = {"server_count": len(self.bot.guilds)}
        async with self.session.post(
            f"{self.BASE_URL}/bots/{self.bot.user.id}/stats", json=server_count
        ) as r:
            try:
                r.raise_for_status()
            except aiohttp.ClientResponseError as e:
                await utils.error_handle(self.bot, e)

    @naff.slash_command(
        name="vote",
        description="Vote for the bot on top.gg.",
    )
    async def vote(self, ctx: utils.RealmContext):
        await ctx.send(f"https://top.gg/bot/{self.bot.user.id}/vote")


def setup(bot):
    importlib.reload(utils)
    Voting(bot)
