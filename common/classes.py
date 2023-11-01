"""
Copyright 2020-2023 AstreaTSS.
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

import asyncio
import typing
from copy import copy

import interactions as ipy
import orjson
import redis.asyncio as aioredis
from prisma._async_http import Response


def valid_channel_check(channel: ipy.GuildChannel) -> ipy.GuildText:
    if not isinstance(channel, ipy.MessageableMixin):
        raise ipy.errors.BadArgument(f"Cannot send messages in {channel.name}.")

    perms = channel.permissions

    if not perms:
        raise ipy.errors.BadArgument(f"Cannot resolve permissions for {channel.name}.")

    if (
        ipy.Permissions.VIEW_CHANNEL not in perms
    ):  # technically pointless, but who knows
        raise ipy.errors.BadArgument(f"Cannot read messages in {channel.name}.")
    elif ipy.Permissions.SEND_MESSAGES not in perms:
        raise ipy.errors.BadArgument(f"Cannot send messages in {channel.name}.")
    elif ipy.Permissions.EMBED_LINKS not in perms:
        raise ipy.errors.BadArgument(
            f"Cannot send embeds (controlled through `Embed Links`) in {channel.name}."
        )

    return channel  # type: ignore


class ValidChannelConverter(ipy.Converter):
    async def convert(
        self, ctx: ipy.InteractionContext, argument: ipy.GuildText
    ) -> ipy.GuildText:
        return valid_channel_check(argument)


class _Placeholder:
    pass


class OrderedSet[T]:
    def __init__(self, an_iter: typing.Iterable[T] | None = None, /) -> None:
        self._dict: dict[T, T] = {}

        if an_iter is not None:
            self._dict = {element: element for element in an_iter}

    def __contains__(self, element: T) -> bool:
        return self._dict.get(element, _Placeholder) != _Placeholder

    def __len__(self) -> int:
        return len(self._dict)

    def __iter__(self) -> typing.Iterator[T]:
        return iter(self._dict)

    def add(self, element: T) -> None:
        self._dict[element] = element

    def remove(self, element: T) -> None:
        self._dict.pop(element)

    def discard(self, element: T) -> None:
        self._dict.pop(element, None)

    def pop(self, element: T) -> T:
        return self._dict.pop(element)

    def clear(self) -> None:
        self._dict.clear()

    def copy(self) -> typing.Self:
        return copy(self)

    def intersection(self, *others: typing.Iterable[T]) -> typing.Self:
        return self.__class__(e for sub in others for e in sub if e in self)

    def __and__(self, other: typing.Iterable[T]) -> typing.Self:
        return self.intersection(other)

    def union(self, *others: typing.Iterable[T]) -> typing.Self:
        return self.__class__(self, *(e for sub in others for e in sub))

    def __or__(self, other: typing.Iterable[T]) -> typing.Self:
        return self.union(other)


# left here just in case you want to use it
class SemaphoreRedis(aioredis.Redis):
    def __init__(self, **kwargs: typing.Any) -> None:
        semaphore_value = kwargs.pop("semaphore_value", 1)
        super().__init__(**kwargs)
        self.connection_pool.connection_kwargs.pop("semaphore_value", None)
        self.semaphore = asyncio.BoundedSemaphore(semaphore_value)

    async def execute_command(
        self, *args: typing.Any, **options: typing.Any
    ) -> typing.Any:
        async with self.semaphore:
            return await super().execute_command(*args, **options)


class FastResponse(Response):
    async def json(self, **kwargs: typing.Any) -> typing.Any:
        return orjson.loads(await self.original.aread(), **kwargs)


Response.json = FastResponse.json  # type: ignore
