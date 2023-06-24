import asyncio
import typing

import aiohttp
import attrs
import interactions as ipy
import redis.asyncio as aioredis
from interactions.models.discord.guild import Guild
from interactions.models.discord.user import Member

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
        return [
            m
            for m_id in self._member_ids
            if (m := self._client.cache.get_member(self.id, m_id))
        ]

    @property
    def roles(self) -> list[ipy.Role]:
        return sorted(
            (
                role
                for r_id in self._role_ids
                if (role := self._client.cache.get_role(r_id))
            ),
            reverse=True,
        )


@attrs.define(eq=False, order=False, hash=False, kw_only=True)
class PatchedMember(Member):
    permissions: typing.Optional[ipy.Permissions] = attrs.field(
        repr=False, default=None, converter=ipy.utils.optional(ipy.Permissions)
    )
    """Calculated permissions for the member, only given in slash commands"""


Guild.__init__ = PatchedGuild.__init__
Guild.from_dict = PatchedGuild.from_dict
Guild.from_list = PatchedGuild.from_list

Member.__init__ = PatchedMember.__init__
Member.from_dict = PatchedMember.from_dict
Member.from_list = PatchedMember.from_list


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


class BetterResponse(aiohttp.ClientResponse):
    def raise_for_status(self) -> None:
        # i just dont want the resp to close lol
        if not self.ok:
            # reason should always be not None for a started response
            assert self.reason is not None  # noqa: S101
            raise aiohttp.ClientResponseError(
                self.request_info,
                self.history,
                status=self.status,
                message=self.reason,
                headers=self.headers,
            )
