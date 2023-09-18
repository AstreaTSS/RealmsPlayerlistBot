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
import contextlib
import inspect
import re
import typing

import attrs
import discord_typings
import interactions as ipy
from interactions.ext import paginators
from interactions.ext import prefixed_commands as prefixed
from interactions.models.discord.emoji import process_emoji

import common.utils as utils

# i use spaces, so...
DOUBLE_TAB = re.compile(r" {8}")


@ipy.utils.define(kw_only=False)
class CustomTimeout(paginators.Timeout):
    if typing.TYPE_CHECKING:
        paginator: "HelpPaginator"

    async def __call__(self) -> None:
        while self.run:
            try:
                await asyncio.wait_for(
                    self.ping.wait(), timeout=self.paginator.timeout_interval
                )
            except asyncio.TimeoutError:
                if self.paginator.message:
                    with contextlib.suppress(ipy.errors.HTTPException):
                        await self.paginator.message.edit(
                            components=[],
                            context=self.paginator.context,
                        )
                return
            else:
                self.ping.clear()


async def callback(ctx: ipy.ComponentContext) -> None:
    """Shows how to use the bot"""

    embed = ipy.Embed(color=ctx.bot.color)

    embed.title = "Using this command"
    embed.description = "Hello! Welcome to the help page."

    entries = (
        ("<argument>", "This means the argument is __**required**__."),
        (
            "[argument]",
            (
                "This means the argument is __**optional**__.\n\n__**Do not type in the"
                " brackets!**__"
            ),
        ),
    )

    embed.add_field(
        name="How do I use this bot?",
        value="Reading the bot signature is pretty simple.",
    )

    for name, value in entries:
        embed.add_field(name=name, value=value, inline=False)

    await ctx.send(embed=embed, ephemeral=True)


@ipy.utils.define(kw_only=False, auto_detect=True)
class HelpPaginator(paginators.Paginator):
    callback: typing.Callable[..., typing.Coroutine] = attrs.field(default=callback)
    """A coroutine to call should the select button be pressed"""
    wrong_user_message: str = attrs.field(
        default="You are not allowed to use this paginator."
    )
    """The message to be sent when the wrong user uses this paginator."""

    callback_button_emoji: typing.Optional[
        typing.Union["ipy.PartialEmoji", dict, str]
    ] = attrs.field(default="❔", metadata=ipy.utils.export_converter(process_emoji))
    """The emoji to use for the callback button."""
    show_callback_button: bool = attrs.field(default=True)
    """Show a button which will call the `callback`"""
    show_select_menu: bool = attrs.field(default=True)
    """Should a select menu be shown for navigation"""

    context: ipy.InteractionContext | None = attrs.field(
        default=None, init=False, repr=False
    )

    @classmethod
    def create_from_list(
        cls,
        client: "ipy.Client",
        content: list[str],
        prefix: str = "",
        suffix: str = "",
        page_size: int = 4000,
        timeout: int = 0,
        default_title: str | None = None,
        default_color: ipy.Color = ipy.BrandColors.BLURPLE,
    ) -> "paginators.Paginator":
        """
        Create a paginator from a list of strings. Useful to maintain formatting.

        Args:
            client: A reference to the client
            content: The content to paginate
            prefix: The prefix for each page to use
            suffix: The suffix for each page to use
            page_size: The maximum characters for each page
            timeout: A timeout to wait before closing the paginator
            default_title: The title to use for the embeds
            default_color: The color to use for the embeds

        Returns:
            A paginator system
        """
        pages = []
        page_length = 0
        page = ""
        for entry in content:
            if len(page) + len(f"\n{entry}") <= page_size:
                page += f"{entry}\n"
            else:
                pages.append(
                    paginators.Page(
                        page, f"Page {page_length + 1}", prefix=prefix, suffix=suffix
                    )
                )
                page_length += 1
                page = ""
        if page != "":
            pages.append(
                paginators.Page(
                    page, f"Page {page_length + 1}", prefix=prefix, suffix=suffix
                )
            )
        return cls(
            client,
            pages=pages,
            timeout_interval=timeout,
            show_callback_button=False,
            default_title=default_title,
            default_color=default_color,
        )

    def create_components(self, disable: bool = False) -> list[ipy.ActionRow]:
        rows = super().create_components()

        if self.show_select_menu:
            current = self.pages[self.page_index]
            rows[0].components[0] = ipy.StringSelectMenu(
                [
                    ipy.StringSelectOption(
                        label=(
                            f"{i+1}:"
                            f" {p.get_summary if isinstance(p, paginators.Page) else p.title}"
                        ),
                        value=str(i),
                    )
                    for i, p in enumerate(self.pages)
                ],
                custom_id=f"{self._uuid}|select",
                placeholder=(
                    f"{self.page_index+1}:"
                    f" {current.get_summary if isinstance(current, paginators.Page) else current.title}"
                ),
                max_values=1,
                disabled=disable,
            )

        return rows

    def to_dict(self) -> dict:
        """Convert this paginator into a dictionary for sending."""
        page = self.pages[self.page_index]

        if isinstance(page, paginators.Page):
            page = page.to_embed()
            if self.default_title:
                page.title = self.default_title
        if not (page.author and page.author.name):
            page.set_author(name=f"Page {self.page_index+1}/{len(self.pages)}")
        if not page.color:
            page.color = self.default_color

        return {
            "embeds": [page.to_dict()],
            "components": [c.to_dict() for c in self.create_components()],
        }

    async def send(self, ctx: ipy.BaseContext) -> ipy.Message:
        """
        Send this paginator.

        Args:
            ctx: The context to send this paginator with

        Returns:
            The resulting message

        """

        if isinstance(ctx, ipy.InteractionContext):
            self.context = ctx

        self._message = await ctx.send(**self.to_dict())
        self._author_id = ctx.author.id

        if self.timeout_interval > 1:
            self._timeout_task = CustomTimeout(self)
            ctx.bot.create_task(self._timeout_task())

        return self._message

    async def reply(self, ctx: prefixed.PrefixedContext) -> ipy.Message:
        """
        Reply this paginator to ctx.

        Args:
            ctx: The context to reply this paginator with
        Returns:
            The resulting message
        """
        self._message = await ctx.reply(**self.to_dict())
        self._author_id = ctx.author.id

        if self.timeout_interval > 1:
            self._timeout_task = CustomTimeout(self)
            ctx.bot.create_task(self._timeout_task())

        return self._message


@attrs.define(init=False)
class PermissionsResolver:
    """An attempt to make a class that can handle slash command permissions."""

    default_member_permissions: typing.Optional[ipy.Permissions] = attrs.field(
        default=None
    )

    disabled_for_all_roles: bool = attrs.field(default=False)
    disabled_for_all_channels: bool = attrs.field(default=False)
    allowed_channels: set[int] = attrs.field(factory=set)
    denied_channels: set[int] = attrs.field(factory=set)
    allowed_roles: set[int] = attrs.field(factory=set)
    denied_roles: set[int] = attrs.field(factory=set)
    allowed_users: set[int] = attrs.field(factory=set)
    denied_users: set[int] = attrs.field(factory=set)

    def __init__(
        self,
        default_member_permissions: typing.Optional[ipy.Permissions],
        guild_id: int,
        permissions_data: list[discord_typings.ApplicationCommandPermissionsData],
    ) -> None:
        # set all of the defaults
        self.__attrs_init__(default_member_permissions=default_member_permissions)  # type: ignore
        self.update(guild_id, permissions_data)

    def update(
        self,
        guild_id: int,
        permissions_data: list[discord_typings.ApplicationCommandPermissionsData],
    ) -> None:
        all_channels = guild_id - 1  # const set by discord

        for permission in permissions_data:
            object_id = int(permission["id"])

            if object_id == guild_id:  # @everyone
                self.disabled_for_all_roles = permission["permission"]
                continue
            if object_id == all_channels:
                self.disabled_for_all_channels = permission["permission"]
                continue

            match permission["type"]:  # noqa: E999
                case 1:  # role
                    (
                        self.allowed_roles.add(object_id)
                        if permission["permission"]
                        else self.denied_roles.add(object_id)
                    )
                case 2:  # user
                    (
                        self.allowed_users.add(object_id)
                        if permission["permission"]
                        else self.denied_users.add(object_id)
                    )
                case 3:  # channel
                    (
                        self.allowed_channels.add(object_id)
                        if permission["permission"]
                        else self.denied_channels.add(object_id)
                    )

    def has_permission(
        self,
        channel: ipy.GuildChannel,
        author: ipy.Member,
        author_permissions: ipy.Permissions,
    ) -> bool:
        if ipy.Permissions.ADMINISTRATOR in author_permissions:
            return True

        # channel stuff is checked first
        if (
            self.disabled_for_all_channels
            and int(channel.id) not in self.allowed_channels
        ):
            return False

        if (
            not self.disabled_for_all_channels
            and int(channel.id) in self.denied_channels
        ):
            return False

        # user is prioritized over roles
        if int(author.id) in self.allowed_users:
            return True
        if int(author.id) in self.denied_users:
            return False

        author_roles = author._role_ids
        if self.disabled_for_all_roles:
            # it does not matter if a role above another role re-disables it
            valid_role = any(int(role) in self.allowed_roles for role in author_roles)
        else:
            # so here's where discord becomes weird
            # if this is enabled for any role explictly, it really does not matter
            # what even a higher role says, they cannot take their permission to
            # use the command anyways
            # however, if they are only disabled and never enabled for a command,
            # then its disabled for real
            valid_role = any(
                int(role) in self.allowed_roles for role in author_roles
            ) or all(int(role) not in self.denied_roles for role in author_roles)

        if not valid_role:
            return False

        return (
            all(
                permission in author_permissions
                for permission in self.default_member_permissions
            )
            if self.default_member_permissions
            else True
        )

    def has_permission_ctx(self, ctx: ipy.BaseInteractionContext) -> bool:
        return self.has_permission(ctx.channel, ctx.author, ctx.author_permissions)  # type: ignore


class GuildApplicationCommandPermissionData(typing.TypedDict):
    id: discord_typings.Snowflake
    application_id: discord_typings.Snowflake
    guild_id: discord_typings.Snowflake
    permissions: list[discord_typings.ApplicationCommandPermissionsData]


async def process_bulk_slash_perms(bot: utils.RealmBotBase, guild_id: int) -> None:
    perms: list[GuildApplicationCommandPermissionData] = (
        await bot.http.batch_get_application_command_permissions(  # type: ignore
            int(bot.app.id), guild_id
        )
    )

    guild_perms = {}
    cmds = get_commands_for_scope_by_ids(bot, guild_id)

    for cmd_perm in perms:
        cmd = cmds.get(cmd_perm["id"])
        if not cmd:
            continue

        resolver = PermissionsResolver(
            cmd.default_member_permissions, guild_id, cmd_perm["permissions"]
        )
        guild_perms[int(cmd_perm["id"])] = resolver

    for cmd in (c for i, c in cmds.items() if not guild_perms.get(i)):
        guild_perms[int(cmd.get_cmd_id(guild_id))] = PermissionsResolver(
            cmd.default_member_permissions, guild_id, []
        )

    bot.slash_perms_cache[guild_id] = guild_perms


def _generate_signature(cmd: ipy.SlashCommand) -> str:
    if not cmd.options:
        return ""

    standardized_options = (
        (ipy.SlashCommandOption(**o) if isinstance(o, dict) else o) for o in cmd.options
    )
    signatures: list[str] = [
        f"<{str(option.name)}>" if option.required else f"[{str(option.name)}]"
        for option in standardized_options
    ]
    return " ".join(signatures)


def _generate_bottom_text(cmd: ipy.SlashCommand) -> str:
    if not cmd.options:
        return ""

    standardized_options = (
        (ipy.SlashCommandOption(**o) if isinstance(o, dict) else o) for o in cmd.options
    )
    str_builder = ["__Options:__"]
    str_builder.extend(
        f"`{str(option.name)}` {'' if option.required else '(optional)'} -"
        f" {str(option.description)}"
        for option in standardized_options
    )

    return "\n".join(str_builder)


@attrs.define()
class MiniCommand:
    name: str = attrs.field()
    resolved_name: str = attrs.field()
    description: str = attrs.field()
    type_: typing.Literal["base", "group", "sub"] = attrs.field()
    signature: str = attrs.field()
    slash_command: ipy.SlashCommand = attrs.field()
    extension: typing.Optional[ipy.Extension] = attrs.field(default=None)
    default_member_permissions: typing.Optional[ipy.Permissions] = attrs.field(
        default=None
    )
    subcommands: set["MiniCommand"] = attrs.field(factory=set)

    def __hash__(self) -> int:
        return id(self)

    @classmethod
    def from_slash_command(
        cls,
        cmd: ipy.SlashCommand,
        type_: typing.Literal["base", "group", "sub"],
        *,
        use_docstring: bool = False,
    ) -> typing.Self:
        desc = ""

        if use_docstring:
            callback = getattr(cmd.callback, "func", cmd.callback)
            desc = inspect.getdoc(callback)
            if isinstance(desc, bytes):
                desc = desc.decode("utf-8")
            if desc:
                desc = DOUBLE_TAB.sub("", desc)

        prefix = ""
        if type_ == "group":
            prefix = "group_"
        elif type_ == "sub":
            prefix = "sub_cmd_"

        name = str(getattr(cmd, f"{prefix}name"))
        resolved_name = f"{(cmd.resolved_name.split(name)[0].strip())} {name}".strip()

        if not desc:
            desc = str(getattr(cmd, f"{prefix}description"))

        if use_docstring:
            desc = desc + "\n\n" + _generate_bottom_text(cmd)

        return cls(
            name=name,
            resolved_name=resolved_name,
            description=desc,
            type_=type_,
            slash_command=cmd,
            extension=cmd.extension,
            default_member_permissions=cmd.default_member_permissions,
            signature=_generate_signature(cmd),
        )

    @property
    def view_subcommands(self) -> list["MiniCommand"]:
        return sorted(self.subcommands, key=lambda x: x.name)

    @property
    def brief_description(self) -> str:
        return self.description.splitlines()[0]

    def add_subcommand(
        self,
        cmd: "MiniCommand",
    ) -> None:
        if self.signature:  # make sure base commands have no signature
            self.signature = ""
        self.subcommands.add(cmd)


def get_commands_for_scope_by_ids(bot: utils.RealmBotBase, guild_id: int) -> dict:
    scope_cmds = bot.interactions_by_scope.get(
        ipy.const.GLOBAL_SCOPE, {}
    ) | bot.interactions_by_scope.get(guild_id, {})
    return {
        v.get_cmd_id(guild_id): v
        for v in scope_cmds.values()
        if isinstance(v, ipy.SlashCommand)
    }


def get_mini_commands_for_scope(
    bot: utils.RealmBotBase, guild_id: int
) -> dict[str, MiniCommand]:
    if (
        mini_cmds := bot.mini_commands_per_scope.get(guild_id, ipy.MISSING)
    ) is not ipy.MISSING:
        return mini_cmds  # type: ignore

    scope_cmds = bot.interactions_by_scope.get(
        ipy.const.GLOBAL_SCOPE, {}
    ) | bot.interactions_by_scope.get(guild_id, {})
    commands = [v for v in scope_cmds.values() if isinstance(v, ipy.SlashCommand)]

    top_level = {c for c in commands if not c.is_subcommand}
    has_one_level_down = {c for c in commands if c.sub_cmd_name and not c.group_name}
    has_two_levels_down = {c for c in commands if c.group_name}

    commands_dict: dict[str, MiniCommand] = {
        cmd.resolved_name: MiniCommand.from_slash_command(
            cmd, "base", use_docstring=True
        )
        for cmd in top_level
    }
    for cmd in has_one_level_down:
        if commands_dict.get(str(cmd.name), ipy.MISSING) is ipy.MISSING:
            commands_dict[str(cmd.name)] = MiniCommand.from_slash_command(cmd, "base")

        base_mini_cmd = commands_dict[str(cmd.name)]
        mini_cmd = MiniCommand.from_slash_command(cmd, "sub", use_docstring=True)
        base_mini_cmd.add_subcommand(mini_cmd)
        commands_dict[cmd.resolved_name] = mini_cmd

    for cmd in has_two_levels_down:
        if commands_dict.get(str(cmd.name), ipy.MISSING) is ipy.MISSING:
            commands_dict[str(cmd.name)] = MiniCommand.from_slash_command(cmd, "base")

        base_mini_cmd = commands_dict[str(cmd.name)]

        group_name = f"{str(cmd.name)} {str(cmd.group_name)}"
        if commands_dict.get(group_name, ipy.MISSING) is ipy.MISSING:
            commands_dict[group_name] = MiniCommand.from_slash_command(cmd, "group")

        group_mini_cmd = commands_dict[group_name]
        base_mini_cmd.add_subcommand(group_mini_cmd)

        mini_cmd = MiniCommand.from_slash_command(cmd, "sub", use_docstring=True)
        group_mini_cmd.add_subcommand(mini_cmd)
        commands_dict[cmd.resolved_name] = mini_cmd

    bot.mini_commands_per_scope[guild_id] = commands_dict
    return commands_dict
