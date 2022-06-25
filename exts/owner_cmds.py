import asyncio
import contextlib
import importlib
import io
import os
import platform
import textwrap
import traceback
import typing
import unicodedata

import aiohttp
import naff
from naff.ext import paginators
from naff.ext.debug_extension.utils import debug_embed
from naff.ext.debug_extension.utils import get_cache_state

import common.utils as utils
from common.clubs_playerlist import fill_in_data_from_clubs
from common.models import GuildConfig
from common.models import RealmPlayer
from common.realms_api import RealmsAPIException

DEV_GUILD_ID = int(os.environ["DEV_GUILD_ID"])


class OwnerCMDs(utils.Extension):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.name = "Owner"

        self.add_ext_check(naff.checks.is_owner())

    def _ascii_name(self, name):
        # source - https://github.com/daveoncode/python-string-utils/blob/78929d/string_utils/manipulation.py#L433
        return (
            unicodedata.normalize("NFKD", name.lower())
            .encode("ascii", "ignore")
            .decode("utf-8")
        )

    def _limit_to_25(self, mapping: list[dict[str, str]]):
        return mapping[:25]

    async def _autocomplete_guilds(self, ctx: naff.AutocompleteContext, argument: str):
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

    @naff.slash_command(
        name="view-guild",
        description="Displays a guild's config. Can only be used by the bot's owner.",
        scopes=[DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    @naff.slash_option(
        "guild",
        "The guild to view.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    async def view_guild(
        self,
        ctx: utils.RealmContext,
        guild_id: str,
    ):
        guild = self.bot.get_guild(int(guild_id))
        guild_config = await GuildConfig.get(guild_id=int(guild_id))

        prefixes = tuple(f"`{p}`" for p in guild_config.prefixes)

        embed = naff.Embed(
            color=self.bot.color, title=f"Server Config for {guild.name}:"
        )
        playerlist_channel = (
            f"<#{guild_config.playerlist_chan}> ({guild_config.playerlist_chan})"
            if guild_config.playerlist_chan
            else "None"
        )
        embed.description = (
            f"Club ID: {guild_config.club_id}\nRealm ID: {guild_config.realm_id}\n"
            + f"Playerlist Channel: {playerlist_channel}\nOnline Command Enabled?"
            f" {guild_config.online_cmd}\nPrefixes: {', '.join(prefixes)}"
        )

        await ctx.send(embed=embed)

    @view_guild.autocomplete("guild")
    async def view_get_guild(self, ctx, guild, **kwargs):
        await self._autocomplete_guilds(ctx, guild)

    @naff.slash_command(
        name="add-guild",
        description=(
            "Adds a guild to the bot's configs. Can only be used by the bot's owner."
        ),
        scopes=[DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    @naff.slash_option(
        "guild_id",
        "The guild ID for the guild to add.",
        naff.OptionTypes.STRING,
        required=True,
    )
    @naff.slash_option(
        "club_id", "The club ID for the Realm.", naff.OptionTypes.STRING, required=False
    )
    @naff.slash_option(
        "realm_id",
        "The Realm ID for the Realm.",
        naff.OptionTypes.STRING,
        required=False,
    )
    @naff.slash_option(
        "playerlist_chan",
        "The playerlist channel ID for this guild.",
        naff.OptionTypes.STRING,
        required=False,
    )
    @naff.slash_option(
        "online_cmd",
        "Should the online command be able to be used?",
        naff.OptionTypes.BOOLEAN,
        required=False,
    )
    async def add_guild(
        self,
        ctx: utils.RealmContext,
        guild_id: str,
        club_id: str = None,
        realm_id: str = None,
        playerlist_chan: str = None,
        online_cmd: bool = None,
    ):
        kwargs = {"guild_id": int(guild_id), "prefixes": {"!?"}}

        if club_id:
            kwargs["club_id"] = club_id
            if club_id != "None":
                await fill_in_data_from_clubs(self.bot, int(club_id), club_id)
        if realm_id:
            kwargs["realm_id"] = realm_id
            await self.bot.redis.sadd(f"realm-id-{realm_id}", guild_id)
        if playerlist_chan:
            kwargs["playerlist_chan"] = int(playerlist_chan)
        if online_cmd:
            kwargs["online_cmd"] = online_cmd

        await GuildConfig.create(**kwargs)
        await ctx.send("Done!")

    @naff.slash_command(
        name="edit-guild",
        description=(
            "Edits a guild in the bot's configs. Can only be used by the bot's owner."
        ),
        scopes=[DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    @naff.slash_option(
        "guild",
        "The guild to edit.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    @naff.slash_option(
        "club_id", "The club ID for the Realm.", naff.OptionTypes.STRING, required=False
    )
    @naff.slash_option(
        "realm_id",
        "The Realm ID for the Realm.",
        naff.OptionTypes.STRING,
        required=False,
    )
    @naff.slash_option(
        "playerlist_chan",
        "The playerlist channel ID for this guild.",
        naff.OptionTypes.STRING,
        required=False,
    )
    @naff.slash_option(
        "online_cmd",
        "Should the online command be able to be used?",
        naff.OptionTypes.BOOLEAN,
        required=False,
    )
    async def edit_guild(
        self,
        ctx: utils.RealmContext,
        guild: str,
        club_id: str = None,
        realm_id: str = None,
        playerlist_chan: str = None,
        online_cmd: bool = None,
    ):
        guild_config = await GuildConfig.get(guild_id=int(guild))

        if realm_id:
            if old_realm_id := guild_config.realm_id:
                await self.bot.redis.srem(f"realm-id-{old_realm_id}", guild)
                await RealmPlayer.filter(
                    realm_xuid_id__startswith=old_realm_id
                ).delete()

            guild_config.realm_id = realm_id if realm_id != "None" else None
            if realm_id != "None":
                await self.bot.redis.sadd(f"realm-id-{realm_id}", guild)
        if club_id:
            guild_config.club_id = club_id if club_id != "None" else None
            if club_id != "None":
                await fill_in_data_from_clubs(self.bot, int(guild), club_id)
        if playerlist_chan:
            guild_config.playerlist_chan = (
                int(playerlist_chan) if playerlist_chan != "None" else None
            )
        if online_cmd:
            guild_config.online_cmd = online_cmd

        await guild_config.save()
        await ctx.send("Done!")

    @edit_guild.autocomplete("guild")
    async def edit_get_guild(self, ctx, guild, **kwargs):
        await self._autocomplete_guilds(ctx, guild)

    @naff.slash_command(
        name="edit-guild-via-id",
        description=(
            "Edits a guild in the bot's configs. Can only be used by the bot's owner."
        ),
        scopes=[DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    @naff.slash_option(
        "guild_id",
        "The guild ID for the guild to edit.",
        naff.OptionTypes.STRING,
        required=True,
    )
    @naff.slash_option(
        "club_id", "The club ID for the Realm.", naff.OptionTypes.STRING, required=False
    )
    @naff.slash_option(
        "realm_id",
        "The Realm ID for the Realm.",
        naff.OptionTypes.STRING,
        required=False,
    )
    @naff.slash_option(
        "playerlist_chan",
        "The playerlist channel ID for this guild.",
        naff.OptionTypes.STRING,
        required=False,
    )
    @naff.slash_option(
        "online_cmd",
        "Should the online command be able to be used?",
        naff.OptionTypes.BOOLEAN,
        required=False,
    )
    async def edit_guild_via_id(
        self,
        ctx: utils.RealmContext,
        guild_id: str,
        club_id: str = None,
        realm_id: str = None,
        playerlist_chan: str = None,
        online_cmd: bool = None,
    ):
        guild_config = await GuildConfig.get(guild_id=int(guild_id))

        if realm_id:
            if old_realm_id := guild_config.realm_id:
                await self.bot.redis.srem(f"realm-id-{old_realm_id}", guild_id)
                await RealmPlayer.filter(
                    realm_xuid_id__startswith=old_realm_id
                ).delete()

            guild_config.realm_id = realm_id if realm_id != "None" else None
            if realm_id != "None":
                await self.bot.redis.sadd(f"realm-id-{realm_id}", guild_id)
        if club_id:
            guild_config.club_id = club_id if club_id != "None" else None
            if club_id != "None":
                await fill_in_data_from_clubs(self.bot, int(guild_id), club_id)
        if playerlist_chan:
            guild_config.playerlist_chan = (
                int(playerlist_chan) if playerlist_chan != "None" else None
            )
        if online_cmd:
            guild_config.online_cmd = online_cmd

        await guild_config.save()
        await ctx.send("Done!")

    @naff.slash_command(
        name="remove-guild",
        description=(
            "Removes a guild from the bot's configs. Can only be used by the bot's"
            " owner."
        ),
        scopes=[DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    @naff.slash_option(
        "guild_id",
        "The guild ID for the guild to remove.",
        naff.OptionTypes.STRING,
        required=True,
    )
    async def remove_guild(
        self,
        ctx: utils.RealmContext,
        guild_id: str,
    ):
        config = await GuildConfig.get(guild_id=int(guild_id))

        if config.realm_id:
            await RealmPlayer.filter(realm_xuid_id__startswith=config.realm_id).delete()

        await config.delete()
        await ctx.send("Deleted!")

    @naff.slash_command(
        name="join-realm",
        description="Joins a realm. Can only be used by the bot's owner.",
        scopes=[DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    @naff.slash_option(
        "realm_code",
        "The Realm code",
        naff.OptionTypes.STRING,
        required=True,
    )
    async def join_realm(self, ctx: utils.RealmContext, realm_code: str):
        try:
            realm = await ctx.bot.realms.join_realm_from_code(realm_code)
            await ctx.send(f"Realm ID: {realm.id}\nClub ID: {realm.club_id}")
        except RealmsAPIException as e:
            if isinstance(e.error, aiohttp.ClientResponseError):
                await utils.msg_to_owner(
                    ctx.bot,
                    f"Status code: {e.resp.status}\nHeaders: {e.error.headers}\nText:"
                    f" {await e.resp.text()}",
                )
            else:
                await utils.error_handle(self.bot, e.error, ctx)

    @naff.slash_command(
        name="invite-link",
        description=(
            "Sends the invite link for the bot. Can only be used by the bot's owner."
        ),
        scopes=[DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    async def invite_link(self, ctx: utils.RealmContext):
        await ctx.send(
            f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=309238025280&scope=applications.commands%20bot"
        )

    @naff.prefixed_command(aliases=["jsk"])
    async def debug(self, ctx: naff.PrefixedContext):
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
    async def cache_info(self, ctx: naff.PrefixedContext):
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
    async def reload(self, ctx: naff.PrefixedContext, *, module: str):
        """Regrows an extension."""
        self.bot.reload_extension(module)
        await ctx.reply(f"Reloaded `{module}`.")

    @debug.subcommand()
    async def load(self, ctx: naff.PrefixedContext, *, module: str):
        """Grows a scale."""
        self.bot.load_extension(module)
        await ctx.reply(f"Loaded `{module}`.")

    @debug.subcommand(aliases=["unload"])
    async def unload(self, ctx: naff.PrefixedContext, *, module: str) -> None:
        """Sheds a scale."""
        self.bot.unload_extension(module)
        await ctx.reply(f"Unloaded `{module}`.")

    @naff.prefixed_command(aliases=["reloadallextensions"])
    async def reload_all_extensions(self, ctx: naff.PrefixedContext):
        for ext in self.bot.ext:
            self.bot.reload_extension(ext)
        await ctx.reply("All extensions reloaded!")

    @reload.error
    @load.error
    @unload.error
    async def extension_error(self, error: Exception, ctx: naff.PrefixedContext, *args):
        if isinstance(error, naff.errors.CommandCheckFailure):
            return await ctx.reply(
                "You do not have permission to execute this command."
            )
        await utils.error_handle(self.bot, error, ctx)

    @debug.subcommand(aliases=["python", "exc"])
    async def exec(self, ctx: naff.PrefixedContext, *, body: str):
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

        if body.startswith("```") and body.endswith("```"):
            body = "\n".join(body.split("\n")[1:-1])
        else:
            body = body.strip("` \n")

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
            return await ctx.message.reply(
                f"```py\n{stdout.getvalue()}{traceback.format_exc()}\n```"
            )
        else:
            return await self.handle_exec_result(ctx, ret, stdout.getvalue())

    async def handle_exec_result(
        self, ctx: naff.PrefixedContext, result: typing.Any, value: typing.Any
    ):
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
                    icon_url=(result.author.guild_avatar or result.author.avatar).url,
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
            return await result.send(ctx)

        if hasattr(result, "__iter__"):
            l_result = list(result)
            if all(isinstance(r, naff.Embed) for r in result):
                paginator = paginators.Paginator.create_from_embeds(self.bot, *l_result)
                return await paginator.send(ctx)

        if not isinstance(result, str):
            result = repr(result)

        # prevent token leak
        result = result.replace(self.bot.http.token, "[REDACTED TOKEN]")

        if len(result) <= 2000:
            return await ctx.message.reply(f"```py\n{result}```")

        paginator = paginators.Paginator.create_from_string(
            self.bot, result, prefix="```py", suffix="```", page_size=4000
        )
        return await paginator.send(ctx)

    @debug.subcommand()
    async def shell(self, ctx: naff.PrefixedContext, *, cmd: str):
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
        return await paginator.send(ctx)

    @debug.subcommand()
    async def git(self, ctx: naff.PrefixedContext, *, cmd: str):
        """Shortcut for 'debug shell git'. Invokes the system shell."""
        await self.shell.callback(ctx, cmd=f"git {cmd}")

    @debug.subcommand()
    async def pip(self, ctx: naff.PrefixedContext, *, cmd: str):
        """Shortcut for 'debug shell pip'. Invokes the system shell."""
        await self.shell.callback(ctx, cmd=f"pip {cmd}")


def setup(bot):
    importlib.reload(utils)
    OwnerCMDs(bot)
