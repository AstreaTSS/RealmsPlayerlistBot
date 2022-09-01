import asyncio
import contextlib
import functools
import inspect
import typing

import attrs
import discord_typings
import naff
from naff.ext import paginators
from naff.models.discord.emoji import process_emoji

import common.utils as utils


@naff.utils.define(kw_only=False)
class CustomTimeout(paginators.Timeout):
    async def __call__(self) -> None:
        while self.run:
            try:
                await asyncio.wait_for(
                    self.ping.wait(), timeout=self.paginator.timeout_interval
                )
            except asyncio.TimeoutError:
                if self.paginator.message:
                    with contextlib.suppress(naff.errors.NotFound):
                        await self.paginator.message.edit(
                            components=self.paginator.create_components(True)
                        )
                return
            else:
                self.ping.clear()


async def callback(ctx: naff.ComponentContext):
    """Shows how to use the bot"""

    embed = naff.Embed(color=ctx.bot.color)

    embed.title = "Using this command"
    embed.description = "Hello! Welcome to the help page."

    entries = (
        ("<argument>", "This means the argument is __**required**__."),
        (
            "[argument]",
            "This means the argument is __**optional**__.\n\nNow that you know the"
            " basics, it should be noted that...\n__**You do not type in the"
            " brackets!**__",
        ),
    )

    embed.add_field(
        name="How do I use this bot?",
        value="Reading the bot signature is pretty simple.",
    )

    for name, value in entries:
        embed.add_field(name=name, value=value, inline=False)

    await ctx.send(embed=embed, ephemeral=True)


@naff.utils.define(kw_only=False, auto_detect=True)
class HelpPaginator(paginators.Paginator):
    callback: typing.Callable[..., typing.Coroutine] = attrs.field(default=callback)
    """A coroutine to call should the select button be pressed"""
    wrong_user_message: str = attrs.field(
        default="You are not allowed to use this paginator."
    )
    """The message to be sent when the wrong user uses this paginator."""

    callback_button_emoji: typing.Optional[
        typing.Union["naff.PartialEmoji", dict, str]
    ] = attrs.field(default="❔", metadata=naff.utils.export_converter(process_emoji))
    """The emoji to use for the callback button."""
    show_callback_button: bool = attrs.field(default=True)
    """Show a button which will call the `callback`"""
    show_select_menu: bool = attrs.field(default=True)
    """Should a select menu be shown for navigation"""

    def create_components(self, disable=False):
        rows = super().create_components()

        if self.show_select_menu:
            current = self.pages[self.page_index]
            rows[0].components[0] = naff.Select(
                [
                    naff.SelectOption(
                        f"{i+1}:"
                        f" {p.get_summary if isinstance(p, paginators.Page) else p.title}",
                        str(i),
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
            if not page.title and self.default_title:
                page.title = self.default_title
        if not (page.author and page.author.name):
            page.set_author(name=f"Page {self.page_index+1}/{len(self.pages)}")
        if not page.color:
            page.color = self.default_color

        return {
            "embeds": [page.to_dict()],
            "components": [c.to_dict() for c in self.create_components()],
        }

    async def send(self, ctx: naff.Context) -> naff.Message:
        """
        Send this paginator.

        Args:
            ctx: The context to send this paginator with

        Returns:
            The resulting message

        """
        self._message = await ctx.send(**self.to_dict())
        self._author_id = ctx.author.id

        if self.timeout_interval > 1:
            self._timeout_task = CustomTimeout(self)
            asyncio.create_task(self._timeout_task())

        return self._message

    async def reply(self, ctx: naff.PrefixedContext) -> naff.Message:
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
            asyncio.create_task(self._timeout_task())

        return self._message


@attrs.define(init=False)
class PermissionsResolver:
    """An attempt to make a class that can handle slash command permissions."""

    default_member_permissions: typing.Optional[naff.Permissions] = attrs.field(
        default=None
    )

    disabled_for_all_roles: bool = attrs.field(default=False)
    disabled_for_all_channels: bool = attrs.field(default=False)
    allowed_channels: list[int] = attrs.field(factory=list)
    denied_channels: list[int] = attrs.field(factory=list)
    allowed_roles: list[int] = attrs.field(factory=list)
    denied_roles: list[int] = attrs.field(factory=list)
    allowed_users: list[int] = attrs.field(factory=list)
    denied_users: list[int] = attrs.field(factory=list)

    def __init__(
        self,
        default_member_permissions: typing.Optional[naff.Permissions],
        guild_id: int,
        permissions_data: list[discord_typings.ApplicationCommandPermissionsData],
    ):
        # set all of the defaults
        self.__attrs_init__(default_member_permissions=default_member_permissions)  # type: ignore
        self.update(guild_id, permissions_data)

    def update(
        self,
        guild_id: int,
        permissions_data: list[discord_typings.ApplicationCommandPermissionsData],
    ):
        all_channels = guild_id - 1  # const set by discord

        for permission in permissions_data:
            object_id = int(permission["id"])

            if object_id == guild_id:  # @everyone
                self.disabled_for_all_roles = permission["permission"]
                continue
            elif object_id == all_channels:
                self.disabled_for_all_channels = permission["permission"]
                continue

            match permission["type"]:
                case 1:  # role
                    self.allowed_roles.append(object_id) if permission[
                        "permission"
                    ] else self.denied_roles.append(object_id)
                case 2:  # user
                    self.allowed_users.append(object_id) if permission[
                        "permission"
                    ] else self.denied_users.append(object_id)
                case 3:  # channel
                    self.allowed_channels.append(object_id) if permission[
                        "permission"
                    ] else self.denied_channels.append(object_id)

    def has_permission(
        self,
        channel: naff.GuildChannel,
        author: naff.Member,
    ) -> bool:
        if author.has_permission(naff.Permissions.ADMINISTRATOR):
            # bypasses literally everything lol
            return True

        # channel stuff is checked first
        if (
            self.disabled_for_all_channels
            and int(channel.id) not in self.allowed_channels
        ):
            return False
        elif (
            not self.disabled_for_all_channels
            and int(channel.id) in self.denied_channels
        ):
            return False

        # user is prioritized over roles
        if int(author.id) in self.allowed_users:
            return True
        elif int(author.id) in self.denied_users:
            return False

        author_roles = author.roles
        if self.disabled_for_all_roles:
            # it does not matter if a role above another role re-disables it
            valid_role = any(
                int(role.id) in self.allowed_roles for role in author_roles
            )
        else:
            # so here's where discord becomes weird
            # if this is enabled for any role explictly, it really does not matter
            # what even a higher role says, they cannot take their permission to
            # use the command anyways
            # however, if they are only disabled and never enabled for a command,
            # then its disabled for real
            valid_role = any(
                int(role.id) in self.allowed_roles for role in author_roles
            ) or all(int(role.id) not in self.denied_roles for role in author_roles)

        if not valid_role:
            return False

        return (
            author.has_permission(self.default_member_permissions)
            if self.default_member_permissions
            else True
        )

    def has_permission_ctx(self, ctx: naff.Context) -> bool:
        return self.has_permission(ctx.channel, ctx.author)  # type: ignore


class GuildApplicationCommandPermissionData(typing.TypedDict):
    id: discord_typings.Snowflake
    application_id: discord_typings.Snowflake
    guild_id: discord_typings.Snowflake
    permissions: list[discord_typings.ApplicationCommandPermissionsData]


async def process_bulk_slash_perms(bot: utils.RealmBotBase, guild_id: int):
    perms: list[
        GuildApplicationCommandPermissionData
    ] = await bot.http.batch_get_application_command_permissions(  # type: ignore
        int(bot.app.id), guild_id
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
        guild_perms[cmd_perm["id"]] = resolver

    for cmd in (c for i, c in cmds.items() if not guild_perms.get(i)):
        guild_perms[int(cmd.get_cmd_id(guild_id))] = PermissionsResolver(
            cmd.default_member_permissions, guild_id, []
        )

    bot.slash_perms_cache[guild_id] = guild_perms


def _generate_signature(cmd: naff.SlashCommand):
    if not cmd.options:
        return ""

    standardized_options = (
        (naff.SlashCommandOption(**o) if isinstance(o, dict) else o)
        for o in cmd.options
    )
    signatures: list[str] = [
        f"<{str(option.name)}>" if option.required else f"[{str(option.name)}]"
        for option in standardized_options
    ]
    return " ".join(signatures)


def _generate_bottom_text(cmd: naff.SlashCommand):
    if not cmd.options:
        return ""

    standardized_options = (
        (naff.SlashCommandOption(**o) if isinstance(o, dict) else o)
        for o in cmd.options
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
    slash_command: naff.SlashCommand = attrs.field()
    extension: typing.Optional[naff.Extension] = attrs.field(default=None)
    default_member_permissions: typing.Optional[naff.Permissions] = attrs.field(
        default=None
    )
    subcommands: set["MiniCommand"] = attrs.field(factory=set)

    def __hash__(self):
        return id(self)

    @classmethod
    def from_slash_command(
        cls,
        cmd: naff.SlashCommand,
        type_: typing.Literal["base", "group", "sub"],
        *,
        use_docstring: bool = False,
    ):
        desc = ""

        if use_docstring:
            callback = getattr(cmd.callback, "func", cmd.callback)
            desc = inspect.getdoc(callback)
            if isinstance(desc, bytes):
                desc = desc.decode("utf-8")

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
    ):
        self.subcommands.add(cmd)


def get_commands_for_scope_by_ids(bot: utils.RealmBotBase, guild_id: int):
    scope_cmds = bot.interactions.get(
        naff.const.GLOBAL_SCOPE, {}
    ) | bot.interactions.get(guild_id, {})
    return {
        v.get_cmd_id(guild_id): v
        for v in scope_cmds.values()
        if isinstance(v, naff.SlashCommand)
    }


def get_mini_commands_for_scope(bot: utils.RealmBotBase, guild_id: int):
    # sourcery skip: dict-comprehension
    scope_cmds = bot.interactions.get(
        naff.const.GLOBAL_SCOPE, {}
    ) | bot.interactions.get(guild_id, {})
    commands = [v for v in scope_cmds.values() if isinstance(v, naff.SlashCommand)]

    top_level = {c for c in commands if not c.is_subcommand}
    has_one_level_down = {c for c in commands if c.sub_cmd_name and not c.group_name}
    has_two_levels_down = {c for c in commands if c.group_name}

    commands_dict: dict[str, MiniCommand] = {}

    for cmd in top_level:
        commands_dict[cmd.resolved_name] = MiniCommand.from_slash_command(
            cmd, "base", use_docstring=True
        )

    for cmd in has_one_level_down:
        if commands_dict.get(str(cmd.name), naff.MISSING) is naff.MISSING:
            commands_dict[str(cmd.name)] = MiniCommand.from_slash_command(cmd, "base")

        base_mini_cmd = commands_dict[str(cmd.name)]
        mini_cmd = MiniCommand.from_slash_command(cmd, "sub", use_docstring=True)
        base_mini_cmd.add_subcommand(mini_cmd)
        commands_dict[cmd.resolved_name] = mini_cmd

    for cmd in has_two_levels_down:
        if commands_dict.get(str(cmd.name), naff.MISSING) is naff.MISSING:
            commands_dict[str(cmd.name)] = MiniCommand.from_slash_command(cmd, "base")

        base_mini_cmd = commands_dict[str(cmd.name)]

        group_name = f"{str(cmd.name)} {str(cmd.group_name)}"
        if commands_dict.get(group_name, naff.MISSING) is naff.MISSING:
            commands_dict[group_name] = MiniCommand.from_slash_command(cmd, "group")

        group_mini_cmd = commands_dict[group_name]
        base_mini_cmd.add_subcommand(group_mini_cmd)

        mini_cmd = MiniCommand.from_slash_command(cmd, "sub", use_docstring=True)
        group_mini_cmd.add_subcommand(mini_cmd)
        commands_dict[cmd.resolved_name] = mini_cmd

    return commands_dict
