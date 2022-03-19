import importlib
import time

from nextcord.ext import commands

import common.utils as utils
from common.models import GuildConfig


class GeneralCMDS(commands.Cog):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot

    @commands.command()
    async def ping(self, ctx):
        """Pings the bot. Great way of finding out if the bot’s working correctly, but otherwise has no real use."""
        start_time = time.perf_counter()
        ping_discord = round((self.bot.latency * 1000), 2)

        mes = await ctx.send(
            f"Pong!\n`{ping_discord}` ms from Discord.\nCalculating personal ping..."
        )

        end_time = time.perf_counter()
        ping_personal = round(((end_time - start_time) * 1000), 2)

        await mes.edit(
            content=(
                f"Pong!\n`{ping_discord}` ms from Discord.\n`{ping_personal}` ms"
                " personally."
            )
        )

    @commands.group(invoke_without_command=True, aliases=["prefix"], ignore_extra=False)
    async def prefixes(self, ctx: utils.RealmContext):
        """A way of getting all of the prefixes for this server. You can also add and remove prefixes via this command."""

        async with ctx.typing():
            guild_config = await ctx.fetch_config()
            prefixes = tuple(f"`{p}`" for p in guild_config.prefixes)

        if prefixes:
            await ctx.reply(
                f"My prefixes for this server are: {', '.join(prefixes)}, but you can"
                " also mention me."
            )
        else:
            await ctx.reply(
                "I have no prefixes on this server, but you can mention me to run a"
                " command."
            )

    @prefixes.command(ignore_extra=False)
    @utils.proper_permissions()
    async def add(self, ctx: utils.RealmContext, prefix: str):
        """Addes the prefix to the bot for the server this command is used in, allowing it to be used for commands of the bot.
        If it's more than one word or has a space at the end, surround the prefix with quotes so it doesn't get lost.
        Requires Manage Guild permissions."""

        if not prefix:
            raise commands.BadArgument("This is an empty string! I cannot use this.")

        async with ctx.typing():
            guild_config = await ctx.fetch_config()
            if len(guild_config.prefixes) >= 10:
                raise utils.CustomCheckFailure(
                    "You have too many prefixes! You can only have up to 10 prefixes."
                )

            if prefix in guild_config.prefixes:
                raise commands.BadArgument("The server already has this prefix!")

            guild_config.prefixes.add(prefix)
            await guild_config.save()

        await ctx.reply(f"Added `{prefix}`!")

    @prefixes.command(ignore_extra=False, aliases=["delete"])
    @utils.proper_permissions()
    async def remove(self, ctx: utils.RealmContext, prefix):
        """Deletes a prefix from the bot from the server this command is used in. The prefix must have existed in the first place.
        If it's more than one word or has a space at the end, surround the prefix with quotes so it doesn't get lost.
        Requires Manage Guild permissions."""

        async with ctx.typing():
            try:
                guild_config = await ctx.fetch_config()
                guild_config.prefixes.remove(prefix)
                await guild_config.save()

            except KeyError:
                raise commands.BadArgument(
                    "The server doesn't have that prefix, so I can't delete it!"
                )

        await ctx.reply(f"Removed `{prefix}`!")


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(GeneralCMDS(bot))
