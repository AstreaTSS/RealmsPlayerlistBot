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
        name="invite",
        description="Sends the invite link for the bot.",
    )
    async def invite(self, ctx: utils.RealmContext):
        await ctx.send(
            f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}"
            "&permissions=309238025280&scope=applications.commands%20bot"
        )

    @naff.slash_command(
        "support", description="Gives an invite link to the support server."
    )
    async def support(self, ctx: naff.InteractionContext):
        await ctx.send("Support server:\nhttps://discord.gg/NSdetwGjpK")

    @naff.slash_command("about", description="Gives information about the bot.")
    async def about(self, ctx: naff.InteractionContext):
        msg_list = [
            "Hi! I'm the Realms Playerlist Bot, a bot that helps out owners of"
            " Minecraft: Bedrock Edition Realms by showing a log of players who have"
            " joined and left.",
            "I was originally created as a port of another bot that was made for a"
            " singular Realm, but since then I've grown into what you see today.",
            "My usages are largely statistical and informative, as I can be used to"
            " narrow down timeframes or just for tracking activity.",
            "If you want to use me, go ahead and invite me to your server and take a"
            " look at `/config help`!\n",
            "Bot made by Astrea#7171.",
        ]

        about_embed = naff.Embed(
            title="About",
            color=self.bot.color,
            description="\n".join(msg_list),
        )
        about_embed.set_author(
            name=f"{self.bot.user.username}",
            icon_url=(
                f"{ctx.guild.me.display_avatar.url if ctx.guild else self.bot.user.display_avatar.url}"
            ),
        )

        about_embed.add_field(
            name="Support Server", value="[Link](https://discord.gg/NSdetwGjpK)"
        )
        about_embed.add_field(
            name="Source Code",
            value="[Link](https://github.com/Astrea49/RealmsPlayerlistBot)",
        )
        about_embed.add_field(
            name="Support Astrea on Ko-Fi!", value="[Link](https://ko-fi.com/astrea49)"
        )
        about_embed.add_field(
            name="FAQ",
            value="[Link](https://github.com/Astrea49/RealmsPlayerlistBot/wiki/FAQ)",
        )
        about_embed.add_field(
            name="Privacy Policy",
            value="[Link](https://github.com/Astrea49/RealmsPlayerlistBot/wiki/Privacy-Policy)",
        )
        about_embed.add_field(
            name="ToS",
            value="[Link](https://github.com/Astrea49/RealmsPlayerlistBot/wiki/Terms-of-Service)",
        )

        await ctx.send(embed=about_embed)

    @naff.slash_command(
        "gamertag_from_xuid",
        description="Gets the gamertag for a specified XUID.",
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

            await self.bot.redis.setex(
                name=str_xuid,
                time=datetime.timedelta(days=14),
                value=maybe_gamertag,
            )

        await ctx.send(f"`{xuid}`'s gamertag: `{maybe_gamertag}`.")


def setup(bot):
    importlib.reload(utils)
    GeneralCMDS(bot)
