import asyncio
import typing

import interactions as ipy
import redis.asyncio as aioredis

import common.utils as utils


def valid_channel_check(channel: ipy.GuildChannel) -> utils.GuildMessageable:
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

    return channel  # type: ignore


class ValidChannelConverter(ipy.Converter):
    async def convert(
        self, ctx: ipy.InteractionContext, argument: ipy.GuildText
    ) -> utils.GuildMessageable:
        return valid_channel_check(argument)


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
