import asyncio
import typing
from enum import IntEnum

import interactions as ipy
import redis.asyncio as aioredis


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


class PatchedStatus(ipy.Activity):
    def to_dict(self) -> dict:
        return ipy.utils.dict_filter_none(
            {"name": self.name, "type": self.type, "state": self.state, "url": self.url}
        )


if typing.TYPE_CHECKING:
    CustomBucket = ipy.Buckets
else:

    class CustomBucket(IntEnum):
        DEFAULT = 0
        """Default is the same as user"""
        USER = 1
        """Per user cooldowns"""
        GUILD = 2
        """Per guild cooldowns"""
        CHANNEL = 3
        """Per channel cooldowns"""
        MEMBER = 4
        """Per guild member cooldowns"""
        CATEGORY = 5
        """Per category cooldowns"""
        ROLE = 6
        """Per role cooldowns"""

        async def get_key(self, context: "ipy.BaseContext") -> typing.Any:
            if self is CustomBucket.USER:
                return context.author.id
            if self is CustomBucket.GUILD:
                return context.guild_id or context.author.id
            if self is CustomBucket.CHANNEL:
                return context.channel.id
            if self is CustomBucket.MEMBER:
                return (
                    (context.guild_id, context.author.id)
                    if context.guild_id
                    else context.author.id
                )
            if self is CustomBucket.CATEGORY:
                return (
                    await context.channel.parent_id
                    if context.channel.parent
                    else context.channel.id
                )
            if self is CustomBucket.ROLE:
                return (
                    context.author.top_role.id
                    if context.guild_id
                    else context.channel.id
                )
            return context.author.id

        def __call__(self, context: "ipy.BaseContext") -> typing.Any:
            return self.get_key(context)
