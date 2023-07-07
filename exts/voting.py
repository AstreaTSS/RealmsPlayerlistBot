import asyncio
import importlib
import os
import typing

import aiohttp
import attrs
import interactions as ipy

import common.utils as utils


@attrs.define(kw_only=True)
class VoteHandler:
    name: str = attrs.field()
    base_url: str = attrs.field()
    session: aiohttp.ClientSession = attrs.field()
    data_url: str = attrs.field()
    data_callback: typing.Callable[[int], dict[str, typing.Any]] = attrs.field()
    vote_url: str = attrs.field()


class Voting(ipy.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.name = "Voting"

        self.handlers: list[VoteHandler] = []

        if os.environ.get("TOP_GG_TOKEN"):
            self.handlers.append(
                VoteHandler(
                    name="Top.gg",
                    base_url="https://top.gg/api",
                    session=aiohttp.ClientSession(
                        headers={"Authorization": os.environ["TOP_GG_TOKEN"]}
                    ),
                    data_url="/bots/{bot_id}/stats",
                    data_callback=lambda guild_count: {"server_count": guild_count},
                    vote_url="https://top.gg/bot/{bot_id}/vote",
                )
            )

        # if os.environ.get("DBL_TOKEN"):
        #     self.handlers.append(
        #         VoteHandler(
        #             name="Discord Bot List",
        #             base_url="https://discordbotlist.com/api/v1",
        #             session=aiohttp.ClientSession(
        #                 headers={"Authorization": os.environ["DBL_TOKEN"]}
        #             ),
        #             data_url="/bots/{bot_id}/stats",
        #             data_callback=lambda guild_count: {"guilds": guild_count},
        #             vote_url=(
        #                 "https://discordbotlist.com/bots/realms-playerlist-bot/upvote"
        #             ),
        #         )
        #     )

        if not self.handlers:
            raise ValueError("No voting handlers were configured.")

        self.autopost_guild_count.start()

    def drop(self) -> None:
        for handler in self.handlers:
            asyncio.create_task(handler.session.close())

        self.autopost_guild_count.stop()
        super().drop()

    @ipy.Task.create(ipy.IntervalTrigger(minutes=30))
    async def autopost_guild_count(self) -> None:
        server_count = len(self.bot.guilds)

        for handler in self.handlers:
            async with handler.session.post(
                f"{handler.base_url}{handler.data_url.format(bot_id=self.bot.user.id)}",
                json=handler.data_callback(server_count),
            ) as r:
                try:
                    r.raise_for_status()
                except aiohttp.ClientResponseError as e:
                    await utils.error_handle(e)

    @ipy.slash_command(
        name="vote",
        description="Vote for the bot.",
    )
    async def vote(self, ctx: utils.RealmContext) -> None:
        website_votes: list[str] = [
            f"**{handler.name}** - <{handler.vote_url.format(bot_id=self.bot.user.id)}>"
            for handler in self.handlers
        ]
        await ctx.send("\n".join(website_votes))


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    Voting(bot)
