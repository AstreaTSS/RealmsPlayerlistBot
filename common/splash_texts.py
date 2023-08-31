import asyncio
import datetime
import random
import typing

import attrs
import interactions as ipy
from dateutil.relativedelta import relativedelta

import common.utils as utils


@attrs.define(eq=False, order=False, hash=False, slots=False, kw_only=False)
class SplashTextUpdated(ipy.events.BaseEvent):
    pass


# please add new entries to the end of the list
splash_texts = (
    "/online is used more than /playerlist",
    "99% bug free!",
    "Monkeypatch free!",  # for now
    "Verified by Discord!",
    "Singlethreaded!",
    "Made with Python!",
    "sus",
    "| json",  # orjson
    "Also try other Realm bots!",
    "Bread is pain!",
    "Open source!",
    "Watching over some Realms!Technically self-hostable!",
    "Check out the Server Setup Guide!",
    "Pong!",
    "In at least 1 server!",
    "Vote Receieved!",  # typo is purposeful
    "RPL!",  # internal codename
    "Using the Realm API!",
    "Use #help-forum!What's a guild?",  # a two in one: guilds are servers, and the bot doesn't store guild object
    "Now with shards!",
    "Not associated with Microsoft!",
    "Never dig down!",
    "This is enough splash texts for a bot, right?",
    "i use ubuntu btw",  # at least, the hosted version does
    "Typehint your code correctly, Polls!",  # please
    "rpl.astrea.cc is not a good subdomain for SEO",  # i should change it one day
    "Running every hour!",
    "1% sugar!",
    "Made with love!",
    "Not associated with Mojang!",
    "Powered by elytras!",  # elytra-ms
    "Excel is a mess!",  # /premium export
    "Thanks, wiki.vg!",
    "Powered by tortoises!",  # tortoise-orm
    "soon™",
    "PURPOSELY_INVALID_KEY_AAAAAAAAAAAAAAAA",  # actually used in the bot
    "Watching players on Realms!",
    "Do bots dream of electric sheep?",
    "Python 3.11!",
    "Now in purple!",
    "Keyboard compatible!",
    "Made by AstreaTSS!",
    "This is good for Realms.",  # actual splash text in mc proper
    "config = await ctx.fetch_config()",  # used too often
    "Cloud computing!",
    "Typehinted!",
    "The Xbox API is a mess!",
    "As seen on Top.gg!",
    "Full of stars!",  # astrea, stars, ha
    "How to get bot?",
    "You can deal with whitespace!",  # people, i swear, its fine, you'll live using python
    "Made with interactions.py!",
    "Imagine being called Generic Realm Bot",  # old name for the bot
    "asyncio is okay!",
    "Made with snakes!",  # python
    "Saved by Mojang!",  # that was wild
    "As seen on GitHub!",
    "What does TSS mean?",  # the star sorceress
    "I don't think, therefore I am not",
    "Since 2020!",
    "What's the square root of a fish?",  # now im sad...
    "Medium-sized!",
    "Check out Playerlist Premium!",
    "Uses slash commands!",
)


class SplashTexts:
    __slots__ = (
        "current_index",
        "bot",
        "splash_texts_length",
        "task",
    )

    def __init__(self, bot: utils.RealmBotBase, current_index: int) -> None:
        self.current_index = current_index
        self.bot = bot
        self.splash_texts_length = len(splash_texts)
        self.task: asyncio.Task | None = None

    @classmethod
    async def from_bot(cls, bot: utils.RealmBotBase) -> typing.Self:
        current_index = await bot.redis.get("rpl-splash-text")
        if current_index is None:
            current_index = random.randint(0, len(splash_texts) - 1)  # noqa: S311
            await bot.redis.set("rpl-splash-text", current_index)
        else:
            current_index = int(current_index)
        return cls(bot, current_index)

    def get(self) -> str:
        return splash_texts[self.current_index]

    async def start(self) -> None:
        self.task = asyncio.create_task(self._task_func())

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()

    async def _task_func(self) -> None:
        while True:
            now = datetime.datetime.now(datetime.UTC)
            next_day = now + relativedelta(
                days=+1, hour=0, minute=0, second=0, microsecond=0
            )
            await utils.sleep_until(next_day)
            await self.next()
            self.bot.dispatch(SplashTextUpdated())

    async def next(self) -> None:
        self.current_index += 1
        if self.current_index >= self.splash_texts_length:
            self.current_index = 0
        await self.bot.redis.set("rpl-splash-text", str(self.current_index))
