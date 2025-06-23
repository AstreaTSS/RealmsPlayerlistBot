"""
Copyright 2020-2025 AstreaTSS.
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

import typing
import uuid
from collections.abc import MutableSet
from copy import copy

import aiohttp
import attrs
import elytra
import humanize
import interactions as ipy
from httpcore._backends import anyio
from httpcore._backends.asyncio import AsyncioBackend

import common.models as models
import common.playerlist_utils as pl_utils
import common.utils as utils
from common.help_tools import CustomTimeout


def valid_channel_check(channel: ipy.GuildChannel) -> ipy.GuildText:
    if not isinstance(channel, ipy.MessageableMixin):
        raise ipy.errors.BadArgument(f"Cannot send messages in {channel.mention}.")

    perms = channel.permissions

    if not perms:
        raise ipy.errors.BadArgument(
            f"Cannot resolve permissions for {channel.mention}."
        )

    if (
        ipy.Permissions.VIEW_CHANNEL not in perms
    ):  # technically pointless, but who knows
        raise ipy.errors.BadArgument(f"Cannot read messages in {channel.mention}.")
    elif ipy.Permissions.SEND_MESSAGES not in perms:
        raise ipy.errors.BadArgument(f"Cannot send messages in {channel.mention}.")
    elif ipy.Permissions.EMBED_LINKS not in perms:
        raise ipy.errors.BadArgument(
            "Cannot send embeds (controlled through `Embed Links`) in"
            f" {channel.mention}."
        )

    return channel  # type: ignore


class ValidChannelConverter(ipy.Converter):
    async def convert(
        self, _: ipy.InteractionContext, argument: ipy.GuildText
    ) -> ipy.GuildText:
        channel = valid_channel_check(argument)

        # im 90% sure discord's channel permission property is broken,
        # so we'll just try to send a message and see if it errors out
        try:
            msg = await channel.send(embed=utils.make_embed("Testing..."))
            await msg.delete()
        except ipy.errors.HTTPException as e:
            if isinstance(e, ipy.errors.Forbidden):
                if e.text == "Missing Permissions":
                    raise ipy.errors.BadArgument(
                        "Cannot send messages and/or send embeds (controlled through"
                        f" `Embed Links`) in {channel.mention}."
                    ) from None
                elif e.text == "Missing Access":
                    raise ipy.errors.BadArgument(
                        f"Cannot read messages in {channel.mention}."
                    ) from None
                else:
                    raise ipy.errors.BadArgument(
                        f"Cannot use {channel.mention}. Please check its permissions."
                    ) from None

            if e.status >= 500:
                raise ipy.errors.BadArgument(
                    "Discord is having issues. Try again later."
                ) from None

            raise e

        return channel


class _Placeholder:
    pass


class OrderedSet[T](MutableSet[T]):
    def __init__(self, an_iter: typing.Iterable[T] | None = None, /) -> None:
        self._dict: dict[T, T] = {}

        if an_iter is not None:
            self._dict = {element: element for element in an_iter}

    def __repr__(self) -> str:
        if not self:
            return f"{self.__class__.__name__}()"
        return f"{self.__class__.__name__}({list(self)!r})"

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


@ipy.utils.define(kw_only=False, auto_detect=True)
class DynamicLeaderboardPaginator:
    client: "utils.RealmBotBase" = attrs.field(
        repr=False,
    )
    """The client to hook listeners into"""

    pages_data: list[tuple[str, int]] = attrs.field(repr=False, kw_only=True)
    """The entries for the leaderboard"""
    period_str: str = attrs.field(repr=False, kw_only=True)
    """The period, represented as a string."""
    timestamp: ipy.Timestamp = attrs.field(repr=False, kw_only=True)
    """The timestamp to use for the embeds."""
    nicknames: dict[str, str] = attrs.field(repr=False, kw_only=True)
    """The nicknames to use for this leaderboard."""

    page_index: int = attrs.field(repr=False, kw_only=True, default=0)
    """The index of the current page being displayed"""
    timeout_interval: int = attrs.field(repr=False, default=120, kw_only=True)
    """How long until this paginator disables itself"""

    context: ipy.InteractionContext | None = attrs.field(
        default=None, init=False, repr=False
    )

    _uuid: str = attrs.field(repr=False, init=False, factory=uuid.uuid4)
    _message: ipy.Message = attrs.field(repr=False, init=False, default=ipy.MISSING)
    _timeout_task: CustomTimeout = attrs.field(
        repr=False, init=False, default=ipy.MISSING
    )
    _author_id: ipy.Snowflake_Type = attrs.field(
        repr=False, init=False, default=ipy.MISSING
    )

    def __attrs_post_init__(self) -> None:
        self.bot.add_component_callback(
            ipy.ComponentCommand(
                name=f"Paginator:{self._uuid}",
                callback=self._on_button,
                listeners=[
                    f"{self._uuid}|select",
                    f"{self._uuid}|first",
                    f"{self._uuid}|back",
                    f"{self._uuid}|next",
                    f"{self._uuid}|last",
                ],
            )
        )

    @property
    def bot(self) -> "utils.RealmBotBase":
        return self.client

    @property
    def message(self) -> ipy.Message:
        """The message this paginator is currently attached to"""
        return self._message

    @property
    def author_id(self) -> ipy.Snowflake_Type:
        """The ID of the author of the message this paginator is currently attached to"""
        return self._author_id

    @property
    def last_page_index(self) -> int:
        return 0 if len(self.pages_data) == 0 else (len(self.pages_data) - 1) // 20

    def create_components(self, disable: bool = False) -> list[ipy.ActionRow]:
        """
        Create the components for the paginator message.

        Args:
            disable: Should all the components be disabled?

        Returns:
            A list of ActionRows

        """
        lower_index = max(0, min((self.last_page_index + 1) - 25, self.page_index - 12))

        output: list[ipy.Button | ipy.StringSelectMenu] = [
            ipy.StringSelectMenu(
                *(
                    ipy.StringSelectOption(label=f"Page {i+1}", value=str(i))
                    for i in range(
                        lower_index,
                        min(self.last_page_index + 1, lower_index + 25),
                    )
                ),
                custom_id=f"{self._uuid}|select",
                placeholder=f"Page {self.page_index+1}",
                max_values=1,
                disabled=disable,
            ),
            ipy.Button(
                style=ipy.ButtonStyle.BLURPLE,
                emoji="⏮️",
                custom_id=f"{self._uuid}|first",
                disabled=disable or self.page_index == 0,
            ),
            ipy.Button(
                style=ipy.ButtonStyle.BLURPLE,
                emoji="⬅️",
                custom_id=f"{self._uuid}|back",
                disabled=disable or self.page_index == 0,
            ),
            ipy.Button(
                style=ipy.ButtonStyle.BLURPLE,
                emoji="➡️",
                custom_id=f"{self._uuid}|next",
                disabled=disable or self.page_index >= self.last_page_index,
            ),
            ipy.Button(
                style=ipy.ButtonStyle.BLURPLE,
                emoji="⏭️",
                custom_id=f"{self._uuid}|last",
                disabled=disable or self.page_index >= self.last_page_index,
            ),
        ]
        return ipy.spread_to_rows(*output)

    async def to_dict(self) -> dict:
        """Convert this paginator into a dictionary for sending."""
        page_data = self.pages_data[self.page_index * 20 : (self.page_index * 20) + 20]

        gamertag_map = await pl_utils.get_xuid_to_gamertag_map(
            self.bot, [e[0] for e in page_data if e[0] not in self.nicknames]
        )

        leaderboard_builder: list[str] = []
        index = self.page_index * 20

        for xuid, playtime in page_data:
            precisedelta = humanize.precisedelta(
                playtime, minimum_unit="minutes", format="%0.0f"
            )

            if precisedelta == "1 minutes":  # why humanize
                precisedelta = "1 minute"

            display = models.display_gamertag(
                xuid, gamertag_map[xuid], self.nicknames.get(xuid)
            )

            leaderboard_builder.append(f"**{index+1}\\.** {display} {precisedelta}")

            index += 1

        page = ipy.Embed(
            title=f"Leaderboard for the past {self.period_str}",
            description="\n".join(leaderboard_builder),
            color=self.bot.color,
            timestamp=self.timestamp,
        )
        page.set_author(name=f"Page {self.page_index+1}/{self.last_page_index+1}")

        return {
            "embeds": [page.to_dict()],
            "components": [c.to_dict() for c in self.create_components()],
        }

    async def send(self, ctx: ipy.BaseContext, **kwargs: typing.Any) -> ipy.Message:
        """
        Send this paginator.

        Args:
            ctx: The context to send this paginator with
            **kwargs: Additional options to pass to `send`.

        Returns:
            The resulting message

        """
        if isinstance(ctx, ipy.InteractionContext):
            self.context = ctx

        self._message = await ctx.send(**await self.to_dict(), **kwargs)
        self._author_id = ctx.author.id

        if self.timeout_interval > 1:
            self._timeout_task = CustomTimeout(self)
            self.client.create_task(self._timeout_task())

        return self._message

    async def _on_button(
        self, ctx: ipy.ComponentContext, *_: typing.Any, **__: typing.Any
    ) -> ipy.Message | None:
        if ctx.author.id != self.author_id:
            return await ctx.send(
                "You are not allowed to use this paginator.", ephemeral=True
            )
        if self._timeout_task:
            self._timeout_task.ping.set()
        match ctx.custom_id.split("|")[1]:
            case "first":
                self.page_index = 0
            case "last":
                self.page_index = self.last_page_index
            case "next":
                if (self.page_index + 1) <= self.last_page_index:
                    self.page_index += 1
            case "back":
                if self.page_index >= 1:
                    self.page_index -= 1
            case "select":
                self.page_index = int(ctx.values[0])

        await ctx.edit_origin(**await self.to_dict())
        return None


@ipy.utils.define(kw_only=False, auto_detect=True)
class DynamicRealmMembers(DynamicLeaderboardPaginator):
    pages_data: list[elytra.Player] = attrs.field(repr=False, kw_only=True)
    realm_name: str = attrs.field(repr=False, kw_only=True)
    owner_xuid: str = attrs.field(repr=False, kw_only=True)
    period_str: str = attrs.field(repr=False, kw_only=True, default="", init=False)

    async def to_dict(self) -> dict:
        """Convert this paginator into a dictionary for sending."""
        page_data = self.pages_data[self.page_index * 20 : (self.page_index * 20) + 20]

        gamertag_map = await pl_utils.get_xuid_to_gamertag_map(
            self.client, [p.uuid for p in page_data if p.uuid not in self.nicknames]
        )

        str_builder: list[str] = []
        index = self.page_index * 20

        for player in page_data:
            xuid = player.uuid

            base_display = models.display_gamertag(
                xuid, gamertag_map[xuid], self.nicknames.get(xuid)
            )

            ending = ""

            if xuid == self.owner_xuid:
                ending += "**Owner**"
            elif player.permission.value == "OPERATOR":
                ending += "**Operator**"
            elif player.uuid == self.bot.xbox.auth_mgr.xsts_token.xuid:
                ending += "**This Bot**"
            else:
                ending += player.permission.value.title()

            str_builder.append(f"- {base_display} - {ending}")

            index += 1

        page = ipy.Embed(
            f"Members of {self.realm_name}",
            description="\n".join(str_builder),
            color=self.bot.color,
            timestamp=self.timestamp,
        )
        page.set_author(name=f"Page {self.page_index+1}/{self.last_page_index+1}")

        return {
            "embeds": [page.to_dict()],
            "components": [c.to_dict() for c in self.create_components()],
        }


class BetterResponse(aiohttp.ClientResponse):
    async def aread(self) -> bytes:
        return await self.read()

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


anyio.AnyIOBackend = AsyncioBackend
