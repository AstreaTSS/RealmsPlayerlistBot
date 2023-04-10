import asyncio
import typing

import attrs
import interactions as ipy
import redis.asyncio as aioredis

import common.utils as utils

KT = typing.TypeVar("KT")
VT = typing.TypeVar("VT")
D = typing.TypeVar("D")


@attrs.define(kw_only=True)
class TimedDict(typing.Generic[KT, VT]):
    expires: float = attrs.field(default=60)

    _dict: dict[KT, VT] = attrs.field(factory=dict, init=False)
    _loop: asyncio.AbstractEventLoop = attrs.field(
        factory=asyncio.get_running_loop, init=False
    )
    _timer: typing.Optional[asyncio.TimerHandle] = attrs.field(default=None, init=False)

    def __setitem__(self, key: KT, value: VT) -> None:
        self._dict[key] = value

    def __getitem__(self, key: KT) -> VT:
        return self._dict[key]

    def __delitem__(self, key: KT) -> None:
        del self._dict[key]

    @typing.overload
    def get(self, key: KT) -> typing.Optional[VT]:
        ...

    @typing.overload
    def get(self, key: KT, default: D) -> typing.Union[VT, D]:
        ...

    def get(
        self, key: KT, default: typing.Optional[D] = None
    ) -> typing.Union[VT, D, None]:
        return self._dict.get(key, default)

    @property
    def filled(self) -> bool:
        return bool(self._timer) and self._loop.time() <= self._timer.when()

    def _clear(self) -> None:
        self._dict.clear()
        self._timer = None

    def insert(self, to_insert: dict[KT, VT]) -> None:
        self._dict.update(to_insert)

        if not self.filled:
            self._timer = self._loop.call_later(self.expires, self._clear)

    def add_one(self, key: KT, value: VT) -> None:
        self._dict[key] = value

    def cancel_timer(self) -> None:
        if self._timer:
            self._timer.cancel()


def valid_channel_check(channel: ipy.GuildChannel) -> utils.GuildMessageable:
    if not isinstance(channel, ipy.MessageableMixin):
        raise ipy.errors.BadArgument(f"Cannot send messages in {channel.name}.")

    perms = channel.permissions_for(channel.guild.me)

    if (
        ipy.Permissions.VIEW_CHANNEL not in perms
    ):  # technically pointless, but who knows
        raise ipy.errors.BadArgument(f"Cannot read messages in {channel.name}.")
    elif ipy.Permissions.READ_MESSAGE_HISTORY not in perms:
        raise ipy.errors.BadArgument(f"Cannot read message history in {channel.name}.")
    elif ipy.Permissions.SEND_MESSAGES not in perms:
        raise ipy.errors.BadArgument(f"Cannot send messages in {channel.name}.")
    elif ipy.Permissions.EMBED_LINKS not in perms:
        raise ipy.errors.BadArgument(f"Cannot send embeds in {channel.name}.")

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
