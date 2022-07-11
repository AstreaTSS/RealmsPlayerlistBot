import asyncio
import contextlib
import datetime
import importlib
import os
import time
import typing

import aiohttp
import naff
import pydantic
from xbox.webapi.api.provider.profile.models import ProfileResponse

import common.utils as utils


class GeneralCMDS(utils.Extension):
    def __init__(self, bot):
        self.name = "General"
        self.bot: utils.RealmBotBase = bot

    @naff.slash_command(
        "ping",
        description=(
            "Pings the bot. Great way of finding out if the bot’s working correctly,"
            " but has no real use."
        ),
    )
    async def ping(self, ctx: utils.RealmContext):
        """Pings the bot. Great way of finding out if the bot’s working correctly, but has no real use."""

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

    @naff.slash_command(
        "gamertag_from_xuid", description="Gets the gamertag for a specified XUID."
    )
    @naff.slash_option(
        "xuid", "The XUID of the player to get.", naff.OptionTypes.STRING, required=True
    )
    async def gamertag_from_xuid(self, ctx: utils.RealmContext, xuid: str):
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

        str_xuid = xuid

        async with self.bot.redis_semaphore:
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
                            maybe_gamertag = ProfileResponse.parse_raw(await r.read())

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
                            maybe_gamertag = ProfileResponse.parse_raw(await r.read())

                if not maybe_gamertag:
                    with contextlib.suppress(aiohttp.ClientResponseError):
                        maybe_gamertag = (
                            await self.bot.profile.client.profile.get_profile_by_xuid(
                                xuid
                            )
                        )

        if not maybe_gamertag:
            raise naff.errors.BadArgument(f"Could not find gamertag of XUID `{xuid}`!")

        if isinstance(maybe_gamertag, ProfileResponse):
            maybe_gamertag = next(
                s.value
                for s in maybe_gamertag.profile_users[0].settings
                if s.id == "Gamertag"
            )

            async with self.bot.redis_semaphore:
                await self.bot.redis.setex(
                    name=str_xuid,
                    time=datetime.timedelta(days=14),
                    value=maybe_gamertag,
                )

        await ctx.send(f"`{xuid}`'s gamertag: `{maybe_gamertag}`.")


def setup(bot):
    importlib.reload(utils)
    GeneralCMDS(bot)
