import asyncio
import typing

import attrs
import interactions as ipy
import redis.asyncio as aioredis
from interactions.models.discord.guild import Guild

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


# monkeypatch to work around bugs
@attrs.define(eq=False, order=False, hash=False, kw_only=True)
class PatchedGuild(Guild):
    @property
    def members(self) -> list[ipy.Member]:
        members = (
            self._client.cache.get_member(self.id, m_id) for m_id in self._member_ids
        )
        return [m for m in members if m]

    @property
    def roles(self) -> list[ipy.Role]:
        roles = super().roles
        return [r for r in roles if r]


Guild.__init__ = PatchedGuild.__init__
Guild.from_dict = PatchedGuild.from_dict
Guild.from_list = PatchedGuild.from_list


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
