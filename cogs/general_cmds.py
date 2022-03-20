import asyncio
import contextlib
import datetime
import importlib
import os
import time
import typing

import aiohttp
import pydantic
from nextcord.ext import commands
from xbox.webapi.api.provider.profile.models import ProfileResponse

import common.utils as utils


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
            ctx.bot.cached_prefixes[ctx.guild.id].add(prefix)

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
                ctx.bot.cached_prefixes[ctx.guild.id].remove(prefix)

            except KeyError:
                raise commands.BadArgument(
                    "The server doesn't have that prefix, so I can't delete it!"
                )

        await ctx.reply(f"Removed `{prefix}`!")

    @commands.command()
    async def gamertag_from_xuid(self, ctx: utils.RealmContext, xuid: int):
        """
        Gets the gamertag for a specified XUID.

        Think of XUIDs as Discord user IDs but for Xbox Live -
        they are frequently used both in Minecraft and with this bot.
        Gamertags are like the user's username in a sense.

        For technical reasons, when using the playerlist, the bot has to do a XUID > gamertag lookup.
        This lookup usually works well, but on the rare occasion it does fail, the bot will show
        the XUID of a player instead of their gamertag to at least make sure something is shown about them.

        This command is useful if the bot fails that lookup and displays the XUID to you. This is a reliable
        way of getting the gamertag, provided the XUID provided is correct in the first place.
        """

        str_xuid = str(xuid)

        async with ctx.typing():
            maybe_gamertag: typing.Union[
                str, ProfileResponse, None
            ] = await self.bot.redis.get(str_xuid)

            if not maybe_gamertag:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=2.5)
                ) as session:
                    with contextlib.suppress(asyncio.TimeoutError):
                        async with session.get(
                            f"https://xbl-api.prouser123.me/profile/xuid/{xuid}"
                        ) as r:
                            with contextlib.suppress(pydantic.ValidationError):
                                maybe_gamertag = ProfileResponse.parse_raw(
                                    await r.read()
                                )

                    if not maybe_gamertag:
                        headers = {
                            "X-Authorization": os.environ["OPENXBL_KEY"],
                            "Accept": "application/json",
                            "Accept-Language": "en-US",
                        }
                        async with session.get(
                            f"https://xbl.io/api/v2/account/{xuid}", headers=headers
                        ) as r:
                            with contextlib.suppress(pydantic.ValidationError):
                                maybe_gamertag = ProfileResponse.parse_raw(
                                    await r.read()
                                )

                    if not maybe_gamertag:
                        with contextlib.suppress(aiohttp.ClientResponseError):
                            maybe_gamertag = await self.bot.profile.client.profile.get_profile_by_xuid(
                                xuid
                            )

            if not maybe_gamertag:
                raise commands.BadArgument(f"Could not find gamertag of XUID `{xuid}`!")

            if isinstance(maybe_gamertag, ProfileResponse):
                maybe_gamertag = next(
                    s.value
                    for s in maybe_gamertag.profile_users[0].settings
                    if s.id == "Gamertag"
                )
                await self.bot.redis.setex(
                    name=str_xuid,
                    time=datetime.timedelta(days=14),
                    value=maybe_gamertag,
                )

            await ctx.reply(f"`{xuid}`'s gamertag: {maybe_gamertag}.")


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(GeneralCMDS(bot))
