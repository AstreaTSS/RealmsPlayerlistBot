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
import collections
import contextlib
import importlib
import io
import os
import platform
import textwrap
import traceback
import typing

import aiohttp
import interactions as ipy
import orjson
import tansy
from interactions.ext import paginators
from interactions.ext import prefixed_commands as prefixed
from interactions.ext.debug_extension.utils import debug_embed, get_cache_state
from prisma.types import GuildConfigCreateInput

import common.utils as utils
from common.clubs_playerlist import fill_in_data_from_clubs
from common.models import GuildConfig

DEV_GUILD_ID = int(os.environ["DEV_GUILD_ID"])


class OwnerCMDs(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.name = "Owner"

        self.set_extension_error(self.ext_error)
        self.add_ext_check(ipy.is_owner())

    @tansy.slash_command(
        name="view-guild",
        description="Displays a guild's config. Can only be used by the bot's owner.",
        scopes=[DEV_GUILD_ID],
        default_member_permissions=ipy.Permissions.ADMINISTRATOR,
    )
    async def view_guild(
        self,
        ctx: utils.RealmContext,
        guild_id: str = tansy.Option("The guild to view."),
    ) -> None:
        config = await GuildConfig.prisma().find_unique_or_raise(
            {"guild_id": int(guild_id)}, include={"premium_code": True}
        )

        guild_data = await self.bot.http.get_guild(guild_id)
        guild_name = guild_data["name"]

        realm_name = utils.na_friendly_str(
            self.bot.realm_name_cache.get(config.realm_id)
        )
        if realm_name != "N/A":
            realm_name = f"`{realm_name}`"
        elif config.realm_id:
            realm_name = "Unknown/Not Found"

        embed = await utils.config_info_generate(
            ctx, config, realm_name, diagnostic_info=True
        )
        embed.title = f"Server Config for {guild_name}"
        await ctx.send(embeds=embed)

    @tansy.slash_command(
        name="add-guild",
        description=(
            "Adds a guild to the bot's configs. Can only be used by the bot's owner."
        ),
        scopes=[DEV_GUILD_ID],
        default_member_permissions=ipy.Permissions.ADMINISTRATOR,
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
        data: GuildConfigCreateInput = {"guild_id": int(guild_id)}

        if club_id:
            data["club_id"] = club_id
            if club_id != "None" and realm_id and realm_id != "None":
                await fill_in_data_from_clubs(self.bot, realm_id, club_id)
        if realm_id:
            data["realm_id"] = realm_id
        if playerlist_chan:
            data["playerlist_chan"] = int(playerlist_chan)

        await GuildConfig.prisma().create(data=data)
        await ctx.send("Done!")

    @tansy.slash_command(
        name="edit-guild",
        description=(
            "Edits a guild in the bot's configs. Can only be used by the bot's owner."
        ),
        scopes=[DEV_GUILD_ID],
        default_member_permissions=ipy.Permissions.ADMINISTRATOR,
    )
    async def edit_guild(
        self,
        ctx: utils.RealmContext,
        guild_id: str = tansy.Option("The guild to edit."),
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
        guild_config = await GuildConfig.prisma().find_unique_or_raise(
            {"guild_id": int(guild_id)}
        )

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
        default_member_permissions=ipy.Permissions.ADMINISTRATOR,
    )
    async def remove_guild(
        self,
        ctx: utils.RealmContext,
        guild_id: str = tansy.Option("The guild ID for the guild to remove."),
    ) -> None:
        await GuildConfig.prisma().delete(where={"guild_id": int(guild_id)})
        await ctx.send("Deleted!")

    @prefixed.prefixed_command(aliases=["jsk"])
    async def debug(self, ctx: prefixed.PrefixedContext) -> None:
        """Get basic information about the bot."""
        uptime = ipy.Timestamp.fromdatetime(self.bot.start_time)
        e = debug_embed("General")
        e.set_thumbnail(self.bot.user.avatar.url)
        e.add_field("Operating System", platform.platform())

        e.add_field(
            "Version Info",
            f"interactions.py@{ipy.__version__} | Py@{ipy.__py_version__}",
        )

        e.add_field("Start Time", f"{uptime.format(ipy.TimestampStyles.RelativeTime)}")

        if privileged_intents := [
            i.name for i in self.bot.intents if i in ipy.Intents.PRIVILEGED
        ]:
            e.add_field("Privileged Intents", " | ".join(privileged_intents))

        e.add_field("Loaded Extensions", ", ".join(self.bot.ext))

        e.add_field("Guilds", str(self.bot.guild_count))

        await ctx.reply(embeds=[e])

    @debug.subcommand(aliases=["cache"])
    async def cache_info(self, ctx: prefixed.PrefixedContext) -> None:
        """Get information about the current cache state."""
        e = debug_embed("Cache")

        e.description = f"```prolog\n{get_cache_state(self.bot)}\n```"
        await ctx.reply(embeds=[e])

    @debug.subcommand()
    async def shutdown(self, ctx: prefixed.PrefixedContext) -> None:
        """Shuts down the bot."""
        await ctx.reply("Shutting down 😴")
        await self.bot.stop()

    @debug.subcommand()
    async def reload(self, ctx: prefixed.PrefixedContext, *, module: str) -> None:
        """Regrows an extension."""
        self.bot.reload_extension(module)
        self.bot.slash_perms_cache = collections.defaultdict(dict)
        self.bot.mini_commands_per_scope = {}
        await ctx.reply(f"Reloaded `{module}`.")

    @debug.subcommand()
    async def load(self, ctx: prefixed.PrefixedContext, *, module: str) -> None:
        """Grows a scale."""
        self.bot.load_extension(module)
        self.bot.slash_perms_cache = collections.defaultdict(dict)
        self.bot.mini_commands_per_scope = {}
        await ctx.reply(f"Loaded `{module}`.")

    @debug.subcommand()
    async def unload(self, ctx: prefixed.PrefixedContext, *, module: str) -> None:
        """Sheds a scale."""
        self.bot.unload_extension(module)
        self.bot.slash_perms_cache = collections.defaultdict(dict)
        self.bot.mini_commands_per_scope = {}
        await ctx.reply(f"Unloaded `{module}`.")

    @prefixed.prefixed_command(aliases=["reloadallextensions"])
    async def reload_all_extensions(self, ctx: prefixed.PrefixedContext) -> None:
        for ext in (e.extension_name for e in self.bot.ext.copy().values()):
            self.bot.reload_extension(ext)
        await ctx.reply("All extensions reloaded!")

    @reload.error
    @load.error
    @unload.error
    async def extension_error(
        self, error: Exception, ctx: prefixed.PrefixedContext, *args: typing.Any
    ) -> ipy.Message | None:
        if isinstance(error, ipy.errors.CommandCheckFailure):
            return await ctx.reply(
                "You do not have permission to execute this command."
            )
        await utils.error_handle(error, ctx=ctx)
        return None

    @debug.subcommand(aliases=["python", "exc"])
    async def exec(self, ctx: prefixed.PrefixedContext, *, body: str) -> ipy.Message:
        """Direct evaluation of Python code."""
        await ctx.channel.trigger_typing()
        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
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
        self, ctx: prefixed.PrefixedContext, result: typing.Any, value: typing.Any
    ) -> ipy.Message:
        if result is None:
            result = value or "No Output!"

        await ctx.message.add_reaction("✅")

        if isinstance(result, ipy.Message):
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

        if isinstance(result, ipy.Embed):
            return await ctx.message.reply(embeds=result)

        if isinstance(result, ipy.File):
            return await ctx.message.reply(file=result)

        if isinstance(result, paginators.Paginator):
            return await result.reply(ctx)

        if hasattr(result, "__iter__"):
            l_result = list(result)
            if all(isinstance(r, ipy.Embed) for r in result):
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
    async def shell(self, ctx: prefixed.PrefixedContext, *, cmd: str) -> ipy.Message:
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
        self, ctx: prefixed.PrefixedContext, *, cmd: typing.Optional[str] = None
    ) -> None:
        """Shortcut for 'debug shell git'. Invokes the system shell."""
        await self.shell.callback(ctx, cmd=f"git {cmd}" if cmd else "git")

    @debug.subcommand()
    async def pip(
        self, ctx: prefixed.PrefixedContext, *, cmd: typing.Optional[str] = None
    ) -> None:
        """Shortcut for 'debug shell pip'. Invokes the system shell."""
        await self.shell.callback(ctx, cmd=f"pip {cmd}" if cmd else "pip")

    @debug.subcommand(aliases=["sync-interactions", "sync-cmds", "sync_cmds", "sync"])
    async def sync_interactions(
        self, ctx: prefixed.PrefixedContext, scope: int = 0
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

        async with ctx.channel.typing:
            await self.bot.synchronise_interactions(
                scopes=[scope], delete_commands=True
            )
            self.bot.slash_perms_cache = collections.defaultdict(dict)
            self.bot.mini_commands_per_scope = {}

        await ctx.reply("Done!")

    @debug.subcommand(aliases=["sync-dbl-cmds", "sync-dbl", "sync-dbl-commands"])
    async def sync_dbl_commands(self, ctx: prefixed.PrefixedContext) -> None:
        if not os.environ.get("DBL_TOKEN"):
            raise ipy.errors.BadArgument("DBL_TOKEN is not set.")

        async with ctx.channel.typing:
            data = await self.bot.http.get_application_commands(self.bot.user.id, 0)
            async with aiohttp.ClientSession(
                headers={"Authorization": os.environ["DBL_TOKEN"]}
            ) as session:
                async with session.post(
                    f"https://discordbotlist.com/api/v1/bots/{self.bot.user.id}/commands",
                    json=data,
                ) as r:
                    r.raise_for_status()

        await ctx.reply("Done!")

    @debug.subcommand(aliases=["bl"])
    async def blacklist(self, ctx: utils.RealmPrefixedContext) -> None:
        await ctx.reply(str(ctx.bot.blacklist))

    @blacklist.subcommand(name="add")
    async def bl_add(
        self, ctx: utils.RealmPrefixedContext, snowflake: ipy.SnowflakeObject
    ) -> None:
        if int(snowflake.id) in ctx.bot.blacklist:
            raise ipy.errors.BadArgument("This entry is already in the blacklist.")
        ctx.bot.blacklist.add(int(snowflake.id))
        await ctx.bot.redis.set("rpl-blacklist", orjson.dumps(list(ctx.bot.blacklist)))
        await ctx.reply("Done!")

    @debug.subcommand(aliases=["trigger-autorunning-playerlist", "trigger-autorunner"])
    async def trigger_autorunning_playerlist(
        self, ctx: utils.RealmPrefixedContext
    ) -> None:
        await self.bot.ext["Autorunners"].playerlist_loop(None)  # type: ignore
        await ctx.reply("Done!")

    @debug.subcommand(
        aliases=["trigger-reoccurring-leaderboard", "trigger-reoccurring-lb"]
    )
    async def trigger_reoccurring_leaderboard(
        self,
        ctx: utils.RealmPrefixedContext,
        second_sunday: bool,
        first_monday_of_month: bool,
    ) -> None:
        await self.bot.ext["Autorunners"].reoccurring_lb_loop(  # type: ignore
            second_sunday, first_monday_of_month
        )
        await ctx.reply("Done!")

    @blacklist.subcommand(name="remove", aliases=["delete"])
    async def bl_remove(
        self, ctx: utils.RealmPrefixedContext, snowflake: ipy.SnowflakeObject
    ) -> None:
        if int(snowflake.id) not in ctx.bot.blacklist:
            raise ipy.errors.BadArgument("This entry is not in the blacklist.")
        ctx.bot.blacklist.discard(int(snowflake.id))
        await ctx.bot.redis.set("rpl-blacklist", orjson.dumps(list(ctx.bot.blacklist)))
        await ctx.reply("Done!")

    async def ext_error(
        self,
        error: Exception,
        ctx: ipy.BaseContext,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        if isinstance(ctx, prefixed.PrefixedContext):
            ctx.send = ctx.message.reply  # type: ignore

        if isinstance(error, ipy.errors.CommandCheckFailure):
            if hasattr(ctx, "send"):
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

        if hasattr(ctx, "send"):
            await ctx.send("An error occured. Please check your DMs.")


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    OwnerCMDs(bot)
