import asyncio
import collections
import contextlib
import importlib
import io
import os
import platform
import textwrap
import traceback
import typing
import unicodedata

import naff
import tansy
from naff.ext import paginators
from naff.ext.debug_extension.utils import debug_embed, get_cache_state

import common.utils as utils
from common.clubs_playerlist import fill_in_data_from_clubs
from common.models import GuildConfig

DEV_GUILD_ID = int(os.environ["DEV_GUILD_ID"])


class OwnerCMDs(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.name = "Owner"

        self.set_extension_error(self.ext_error)
        self.add_ext_check(naff.checks.is_owner())

    def _ascii_name(self, name: str) -> str:
        # source - https://github.com/daveoncode/python-string-utils/blob/78929d/string_utils/manipulation.py#L433
        return (
            unicodedata.normalize("NFKD", name.lower())
            .encode("ascii", "ignore")
            .decode("utf-8")
        )

    def _limit_to_25(self, mapping: list[dict[str, str]]) -> list[dict[str, str]]:
        return mapping[:25]

    async def _autocomplete_guilds(
        self, ctx: naff.AutocompleteContext, argument: str
    ) -> None:
        guild_mapping = [
            {"name": guild.name, "value": str(guild.id)} for guild in ctx.bot.guilds
        ]

        if not argument:
            await ctx.send(self._limit_to_25(guild_mapping))
            return

        near_guilds = [
            {"name": guild_dict["name"], "value": guild_dict["value"]}
            for guild_dict in guild_mapping
            if argument.lower() in self._ascii_name(guild_dict["name"])
        ]
        await ctx.send(self._limit_to_25(near_guilds))

    @tansy.slash_command(
        name="view-guild",
        description="Displays a guild's config. Can only be used by the bot's owner.",
        scopes=[DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    async def view_guild(
        self,
        ctx: utils.RealmContext,
        guild: str = tansy.Option("The guild to view.", autocomplete=True),
    ) -> None:
        config = await GuildConfig.get(guild_id=int(guild)).prefetch_related(
            "premium_code"
        )
        actual_guild: naff.Guild = ctx.bot.get_guild(int(guild))

        embed = naff.Embed(
            color=self.bot.color, title=f"Server Config for {actual_guild.name}:"
        )
        playerlist_channel = utils.na_friendly_str(config.playerlist_chan)

        realm_name = utils.na_friendly_str(
            self.bot.realm_name_cache.get(config.realm_id)
        )
        if realm_name != "N/A":
            realm_name = f"`{realm_name}`"
        elif config.realm_id:
            realm_name = "Unknown/Not Found"

        autorunner = utils.toggle_friendly_str(
            bool(config.realm_id and config.playerlist_chan)
        )
        offline_realm_ping = utils.na_friendly_str(config.realm_offline_role)

        embed.description = (
            f"Autorun Playerlist Channel ID: {playerlist_channel}\nRealm Name:"
            f" {realm_name}\nAutorunner: {autorunner}\nOffline Realm Ping Role ID:"
            f" {offline_realm_ping}\n\nPremium Activated:"
            f" {utils.yesno_friendly_str(bool(config.premium_code))}\nLive Playerlist:"
            f" {utils.toggle_friendly_str(config.live_playerlist)}\n\nExtra"
            f" Info:\nRealm ID: {utils.na_friendly_str(config.realm_id)}\nClub ID:"
            f" {utils.na_friendly_str(config.club_id)}"
        )

        await ctx.send(embeds=[embed])

    @view_guild.autocomplete("guild")
    async def view_get_guild(
        self, ctx: naff.AutocompleteContext, guild: str, **kwargs: typing.Any
    ) -> None:
        await self._autocomplete_guilds(ctx, guild)

    @tansy.slash_command(
        name="add-guild",
        description=(
            "Adds a guild to the bot's configs. Can only be used by the bot's owner."
        ),
        scopes=[DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    async def add_guild(
        self,
        ctx: utils.RealmContext,
        guild_id: str = tansy.Option("The guild ID for the guild to add."),
        club_id: typing.Optional[str] = tansy.Option(
            "The club ID for the Realm.", default=None
        ),
        realm_id: typing.Optional[str] = tansy.Option(
            "The Realm ID for the Realm.", default=None
        ),
        playerlist_chan: typing.Optional[str] = tansy.Option(
            "The playerlist channel ID for this guild.", default=None
        ),
    ) -> None:
        kwargs: dict[str, int | str] = {"guild_id": int(guild_id)}

        if club_id:
            kwargs["club_id"] = club_id
            if club_id != "None" and realm_id and realm_id != "None":
                await fill_in_data_from_clubs(self.bot, realm_id, club_id)
        if realm_id:
            kwargs["realm_id"] = realm_id
        if playerlist_chan:
            kwargs["playerlist_chan"] = int(playerlist_chan)

        await GuildConfig.create(**kwargs)
        await ctx.send("Done!")

    @tansy.slash_command(
        name="edit-guild",
        description=(
            "Edits a guild in the bot's configs. Can only be used by the bot's owner."
        ),
        scopes=[DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    async def edit_guild(
        self,
        ctx: utils.RealmContext,
        guild: str = tansy.Option("The guild to edit.", autocomplete=True),
        club_id: typing.Optional[str] = tansy.Option(
            "The club ID for the Realm.", default=None
        ),
        realm_id: typing.Optional[str] = tansy.Option(
            "The Realm ID for the Realm.", default=None
        ),
        playerlist_chan: typing.Optional[str] = tansy.Option(
            "The playerlist channel ID for this guild.", default=None
        ),
    ) -> None:
        guild_config = await GuildConfig.get(guild_id=int(guild))

        if realm_id:
            guild_config.realm_id = realm_id if realm_id != "None" else None
        if club_id:
            guild_config.club_id = club_id if club_id != "None" else None
            if club_id != "None" and guild_config.realm_id:
                await fill_in_data_from_clubs(self.bot, guild_config.realm_id, club_id)
        if playerlist_chan:
            guild_config.playerlist_chan = (
                int(playerlist_chan) if playerlist_chan != "None" else None
            )

        await guild_config.save()
        await ctx.send("Done!")

    @edit_guild.autocomplete("guild")
    async def edit_get_guild(
        self, ctx: naff.AutocompleteContext, guild: str, **kwargs: typing.Any
    ) -> None:
        await self._autocomplete_guilds(ctx, guild)

    @tansy.slash_command(
        name="edit-guild-via-id",
        description=(
            "Edits a guild in the bot's configs. Can only be used by the bot's owner."
        ),
        scopes=[DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    async def edit_guild_via_id(
        self,
        ctx: utils.RealmContext,
        guild_id: str = tansy.Option("The guild ID for the guild to edit."),
        club_id: typing.Optional[str] = tansy.Option(
            "The club ID for the Realm.", default=None
        ),
        realm_id: typing.Optional[str] = tansy.Option(
            "The Realm ID for the Realm.", default=None
        ),
        playerlist_chan: typing.Optional[str] = tansy.Option(
            "The playerlist channel ID for this guild.", default=None
        ),
    ) -> None:
        guild_config = await GuildConfig.get(guild_id=int(guild_id))

        if realm_id:
            guild_config.realm_id = realm_id if realm_id != "None" else None
        if club_id:
            guild_config.club_id = club_id if club_id != "None" else None
            if club_id != "None" and guild_config.realm_id:
                await fill_in_data_from_clubs(self.bot, guild_config.realm_id, club_id)
        if playerlist_chan:
            guild_config.playerlist_chan = (
                int(playerlist_chan) if playerlist_chan != "None" else None
            )

        await guild_config.save()
        await ctx.send("Done!")

    @tansy.slash_command(
        name="remove-guild",
        description=(
            "Removes a guild from the bot's configs. Can only be used by the bot's"
            " owner."
        ),
        scopes=[DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    async def remove_guild(
        self,
        ctx: utils.RealmContext,
        guild_id: str = tansy.Option("The guild ID for the guild to remove."),
    ) -> None:
        await GuildConfig.filter(guild_id=int(guild_id)).delete()
        await ctx.send("Deleted!")

    @naff.prefixed_command(aliases=["jsk"])
    async def debug(self, ctx: naff.PrefixedContext) -> None:
        """Get basic information about the bot."""
        uptime = naff.Timestamp.fromdatetime(self.bot.start_time)
        e = debug_embed("General")
        e.set_thumbnail(self.bot.user.avatar.url)
        e.add_field("Operating System", platform.platform())

        e.add_field(
            "Version Info",
            f"NAFF@{naff.__version__} | Py@{naff.__py_version__}",
        )

        e.add_field("Start Time", f"{uptime.format(naff.TimestampStyles.RelativeTime)}")

        if privileged_intents := [
            i.name for i in self.bot.intents if i in naff.Intents.PRIVILEGED
        ]:
            e.add_field("Privileged Intents", " | ".join(privileged_intents))

        e.add_field("Loaded Extensions", ", ".join(self.bot.ext))

        e.add_field("Guilds", str(len(self.bot.guilds)))

        await ctx.reply(embeds=[e])

    @debug.subcommand(aliases=["cache"])
    async def cache_info(self, ctx: naff.PrefixedContext) -> None:
        """Get information about the current cache state."""
        e = debug_embed("Cache")

        e.description = f"```prolog\n{get_cache_state(self.bot)}\n```"
        await ctx.reply(embeds=[e])

    @debug.subcommand()
    async def shutdown(self, ctx: naff.PrefixedContext) -> None:
        """Shuts down the bot."""
        await ctx.reply("Shutting down 😴")
        await self.bot.stop()

    @debug.subcommand()
    async def reload(self, ctx: naff.PrefixedContext, *, module: str) -> None:
        """Regrows an extension."""
        self.bot.reload_extension(module)
        self.bot.slash_perms_cache = collections.defaultdict(dict)
        self.bot.mini_commands_per_scope = {}
        await ctx.reply(f"Reloaded `{module}`.")

    @debug.subcommand()
    async def load(self, ctx: naff.PrefixedContext, *, module: str) -> None:
        """Grows a scale."""
        self.bot.load_extension(module)
        self.bot.slash_perms_cache = collections.defaultdict(dict)
        self.bot.mini_commands_per_scope = {}
        await ctx.reply(f"Loaded `{module}`.")

    @debug.subcommand()
    async def unload(self, ctx: naff.PrefixedContext, *, module: str) -> None:
        """Sheds a scale."""
        self.bot.unload_extension(module)
        self.bot.slash_perms_cache = collections.defaultdict(dict)
        self.bot.mini_commands_per_scope = {}
        await ctx.reply(f"Unloaded `{module}`.")

    @naff.prefixed_command(aliases=["reloadallextensions"])
    async def reload_all_extensions(self, ctx: naff.PrefixedContext) -> None:
        for ext in (e.extension_name for e in self.bot.ext.copy().values()):
            self.bot.reload_extension(ext)
        await ctx.reply("All extensions reloaded!")

    @reload.error
    @load.error
    @unload.error
    async def extension_error(
        self, error: Exception, ctx: naff.PrefixedContext, *args: typing.Any
    ) -> naff.Message | None:
        if isinstance(error, naff.errors.CommandCheckFailure):
            return await ctx.reply(
                "You do not have permission to execute this command."
            )
        await utils.error_handle(error, ctx=ctx)
        return None

    @debug.subcommand(aliases=["python", "exc"])
    async def exec(self, ctx: naff.PrefixedContext, *, body: str) -> naff.Message:
        """Direct evaluation of Python code."""
        await ctx.channel.trigger_typing()
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "server": ctx.guild,
            "guild": ctx.guild,
            "message": ctx.message,
        } | globals()

        body = (
            "\n".join(body.split("\n")[1:-1])
            if body.startswith("```") and body.endswith("```")
            else body.strip("` \n")
        )

        stdout = io.StringIO()

        to_compile = "async def func():\n%s" % textwrap.indent(body, "  ")
        try:
            exec(to_compile, env)  # noqa: S102
        except SyntaxError:
            return await ctx.reply(f"```py\n{traceback.format_exc()}\n```")

        func = env["func"]
        try:
            with contextlib.redirect_stdout(stdout):
                ret = await func()  # noqa
        except Exception:
            await ctx.message.add_reaction("❌")
            raise
        else:
            return await self.handle_exec_result(ctx, ret, stdout.getvalue())

    async def handle_exec_result(
        self, ctx: naff.PrefixedContext, result: typing.Any, value: typing.Any
    ) -> naff.Message:
        if not result:
            result = value or "No Output!"

        await ctx.message.add_reaction("✅")

        if isinstance(result, naff.Message):
            try:
                e = debug_embed(
                    "Exec", timestamp=result.created_at, url=result.jump_url
                )
                e.description = result.content
                e.set_author(
                    result.author.tag,
                    icon_url=result.author.display_avatar.url,
                )
                e.add_field(
                    "\u200b", f"[Jump To]({result.jump_url})\n{result.channel.mention}"
                )

                return await ctx.message.reply(embeds=e)
            except Exception:
                return await ctx.message.reply(result.jump_url)

        if isinstance(result, naff.Embed):
            return await ctx.message.reply(embeds=result)

        if isinstance(result, naff.File):
            return await ctx.message.reply(file=result)

        if isinstance(result, paginators.Paginator):
            return await result.reply(ctx)

        if hasattr(result, "__iter__"):
            l_result = list(result)
            if all(isinstance(r, naff.Embed) for r in result):
                paginator = paginators.Paginator.create_from_embeds(self.bot, *l_result)
                return await paginator.reply(ctx)

        if not isinstance(result, str):
            result = repr(result)

        # prevent token leak
        result = result.replace(self.bot.http.token, "[REDACTED TOKEN]")

        if len(result) <= 2000:
            return await ctx.message.reply(f"```py\n{result}```")

        paginator = paginators.Paginator.create_from_string(
            self.bot, result, prefix="```py", suffix="```", page_size=4000
        )
        return await paginator.reply(ctx)

    @debug.subcommand()
    async def shell(self, ctx: naff.PrefixedContext, *, cmd: str) -> naff.Message:
        """Executes statements in the system shell."""
        async with ctx.channel.typing:
            process = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )

            output, _ = await process.communicate()
            output_str = output.decode("utf-8")
            output_str += f"\nReturn code {process.returncode}"

        if len(output_str) <= 2000:
            return await ctx.message.reply(f"```sh\n{output_str}```")

        paginator = paginators.Paginator.create_from_string(
            self.bot, output_str, prefix="```sh", suffix="```", page_size=4000
        )
        return await paginator.reply(ctx)

    @debug.subcommand()
    async def git(
        self, ctx: naff.PrefixedContext, *, cmd: typing.Optional[str] = None
    ) -> None:
        """Shortcut for 'debug shell git'. Invokes the system shell."""
        await self.shell.callback(ctx, cmd=f"git {cmd}" if cmd else "git")

    @debug.subcommand()
    async def pip(
        self, ctx: naff.PrefixedContext, *, cmd: typing.Optional[str] = None
    ) -> None:
        """Shortcut for 'debug shell pip'. Invokes the system shell."""
        await self.shell.callback(ctx, cmd=f"pip {cmd}" if cmd else "pip")

    @debug.subcommand(aliases=["sync-interactions", "sync-cmds", "sync_cmds", "sync"])
    async def sync_interactions(
        self, ctx: naff.PrefixedContext, scope: int = 0
    ) -> None:
        """
        Synchronizes all interaction commands with Discord.

        Should not be used lightly.
        """
        # syncing interactions in inherently intensive and
        # has a high risk of running into the ratelimit
        # while this is fine for a small bot where it's unlikely
        # to even matter, for big bots, running into this ratelimit
        # can cause havoc on other functions

        # we only sync to the global scope to make delete_commands
        # a lot better in the ratelimiting department, but i
        # would still advise caution to any self-hosters, and would
        # only suggest using this when necessary
        await self.bot.synchronise_interactions(scopes=[scope], delete_commands=True)
        self.bot.slash_perms_cache = collections.defaultdict(dict)
        self.bot.mini_commands_per_scope = {}

        await ctx.reply("Done!")

    async def ext_error(self, error: Exception, ctx: naff.Context) -> None:
        if isinstance(ctx, naff.PrefixedContext):
            ctx.send = ctx.reply

        if isinstance(error, naff.errors.CommandCheckFailure):
            if isinstance(ctx, naff.SendableContext):
                await ctx.send("Nice try.")
            return

        error_str = utils.error_format(error)
        chunks = utils.line_split(error_str)

        for i in range(len(chunks)):
            chunks[i][0] = f"```py\n{chunks[i][0]}"
            chunks[i][len(chunks[i]) - 1] += "\n```"

        final_chunks = ["\n".join(chunk) for chunk in chunks]
        if ctx and hasattr(ctx, "message") and hasattr(ctx.message, "jump_url"):
            final_chunks.insert(0, f"Error on: {ctx.message.jump_url}")

        to_send = final_chunks
        split = False

        await utils.msg_to_owner(self.bot, to_send, split)

        if isinstance(ctx, naff.SendableContext):
            await ctx.send("An error occured. Please check your DMs.")


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    OwnerCMDs(bot)
