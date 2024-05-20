"""
Copyright 2020-2024 AstreaTSS.
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

import platform
import random
import typing

import attrs
import interactions as ipy
import orjson

import common.utils as utils


@attrs.define(eq=False, order=False, hash=False, slots=False, kw_only=False)
class SplashTextUpdated(ipy.events.BaseEvent):
    pass


# https://docs.python.org/3/library/platform.html?highlight=platform#platform.python_version_tuple
PYTHON_VERSION = platform.python_version_tuple()


# please add new entries to the end of the list
splash_texts: tuple[str, ...] = (
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
    "Watching over some Realms!",
    "Check out the Server Setup Guide!",
    "Pong!",
    "In at least 1 server!",
    "Vote Receieved!",  # typo is purposeful
    "RPL!",  # internal codename
    "Uses the Realms API!",
    "What's a guild?",  # a two in one: guilds are servers, and the bot doesn't store guild object
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
    "Not powered by tortoises!",  # tortoise-orm
    "soon™",
    "PURPOSELY_INVALID_KEY_AAAAAAAAAAAAAAAA",  # actually used in the bot
    "Watching players on Realms!",
    "Do bots dream of electric sheep?",
    f"{platform.python_implementation()} {PYTHON_VERSION[0]}.{PYTHON_VERSION[1]}!",  # ie CPython 3.12
    "Now in purple!",
    "Keyboard compatible!",
    "Made by AstreaTSS!",
    "This is good for Realms!",  # actual splash text in mc proper
    "config = await ctx.fetch_config()",  # used too often
    "Cloud computing!",
    "Typehinted!",
    "The Xbox API is a mess!",
    "As seen on Top.gg!",
    "Full of stars!",  # astrea, stars, ha
    "Technically self-hostable!",
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
    "Powered by prisms!",  # prisma
    "/vote for a cookie!",
    "Help, I'm stuck in a splash text generator",
    "Maybe dockerized!",  # i mean, if you self host, sure
    "It's legal, too!",
    "Created on June 24th, 2020!",
    "Licensed under AGPL!",
)


class SplashTexts:
    __slots__ = (
        "splash_index_list",
        "bot",
        "splash_length",
    )

    def __init__(
        self, bot: utils.RealmBotBase, splash_index_list: list[int], splash_length: int
    ) -> None:
        self.splash_index_list = splash_index_list
        self.bot = bot
        self.splash_length = splash_length

    @classmethod
    async def from_bot(cls, bot: utils.RealmBotBase) -> typing.Self:
        current_index_list = await bot.redis.get("rpl-splash-index-list")
        splash_length = len(splash_texts)

        if current_index_list is None:
            current_index_list = random.sample(range(splash_length), splash_length)
            await bot.redis.set(
                "rpl-splash-index-list", orjson.dumps(current_index_list)
            )
            await bot.redis.set("rpl-splash-length", splash_length)

        else:
            current_index_list = orjson.loads(current_index_list)
            stored_splash_length = int(await bot.redis.get("rpl-splash-length"))

            if stored_splash_length < splash_length:
                # add new indexes to the list, while keeping current first index
                indexes_to_add = list(range(stored_splash_length, splash_length))
                current_index_list = current_index_list[:1] + random.sample(
                    current_index_list[1:] + indexes_to_add,
                    len(current_index_list[1:] + indexes_to_add),
                )
                await bot.redis.set(
                    "rpl-splash-index-list", orjson.dumps(current_index_list)
                )
                await bot.redis.set("rpl-splash-length", len(splash_texts))

            if (
                stored_splash_length > splash_length
            ):  # this should never happen, but just reset
                current_index_list = random.sample(current_index_list, splash_length)
                await bot.redis.set(
                    "rpl-splash-index-list", orjson.dumps(current_index_list)
                )
                await bot.redis.set("rpl-splash-length", len(splash_texts))

        self = cls(bot, current_index_list, splash_length)
        await self.start()
        return self

    def get(self) -> str:
        return splash_texts[self.splash_index_list[0]]

    async def start(self) -> None:
        self._task_func.start()

    async def stop(self) -> None:
        if self._task_func.started:
            self._task_func.stop()

    @ipy.Task.create(ipy.CronTrigger("0 0 * * *"))
    async def _task_func(self) -> None:
        await self.next()

    async def next(self) -> None:
        last_index = self.splash_index_list.pop(0)  # not efficient, but it works

        if not self.splash_index_list:
            self.splash_index_list = random.sample(
                range(self.splash_length), self.splash_length
            )

            if self.splash_index_list[0] == last_index:
                # swap first and third-to-last indexes
                self.splash_index_list[0], self.splash_index_list[-3] = (
                    self.splash_index_list[-3],
                    self.splash_index_list[0],
                )

        await self.bot.redis.set(
            "rpl-splash-index-list", orjson.dumps(self.splash_index_list)
        )
        self.bot.dispatch(SplashTextUpdated())
