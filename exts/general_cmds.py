import asyncio
import contextlib
import datetime
import importlib
import os
import subprocess
import time
import typing

import aiohttp
import naff
import orjson
import tansy
from apischema import ValidationError

import common.models as models
import common.utils as utils
import common.xbox_api as xbox_api
from common.microsoft_core import MicrosoftAPIException


class GeneralCMDS(utils.Extension):
    def __init__(self, bot):
        self.name = "General"
        self.bot: utils.RealmBotBase = bot

    def _get_commit_hash(self):
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .decode("ascii")
            .strip()
        )

    async def get_commit_hash(self):
        return await asyncio.to_thread(self._get_commit_hash)

    @naff.slash_command(
        "ping",
        description=(
            "Pings the bot. Great way of finding out if the bot’s working correctly,"
            " but has no real use."
        ),
    )
    async def ping(self, ctx: utils.RealmContext):
        """
        Pings the bot. Great way of finding out if the bot’s working correctly, but has no real use.
        """

        start_time = time.perf_counter()
        ping_discord = round((self.bot.latency * 1000), 2)

        mes = await ctx.send(
            f"Pong!\n`{ping_discord}` ms from Discord.\nCalculating personal ping..."
        )

        end_time = time.perf_counter()
        ping_personal = round(((end_time - start_time) * 1000), 2)

        await ctx.edit(
            message=mes,
            content=(
                f"Pong!\n`{ping_discord}` ms from Discord.\n`{ping_personal}` ms"
                " personally."
            ),
        )

    @naff.slash_command(
        name="invite",
        description="Sends instructions on how to invite the bot.",
    )
    async def invite(self, ctx: utils.RealmContext):
        await ctx.send(os.environ["SETUP_LINK"])

    @naff.slash_command(
        "support", description="Gives an invite link to the support server."
    )
    async def support(self, ctx: naff.InteractionContext):
        await ctx.send("Support server:\nhttps://discord.gg/NSdetwGjpK")

    @naff.slash_command("about", description="Gives information about the bot.")
    async def about(self, ctx: naff.InteractionContext):
        msg_list = [
            (
                "Hi! I'm the **Realms Playerlist Bot**, a bot that helps out owners of"
                " Minecraft: Bedrock Edition Realms by showing a log of players who"
                " have joined and left."
            ),
            (
                "If you want to use me, go ahead and invite me to your server and take"
                " a look at `/config help`!"
            ),
        ]

        about_embed = naff.Embed(
            title="About",
            color=self.bot.color,
            description="\n".join(msg_list),
        )
        about_embed.set_thumbnail(
            ctx.guild.me.display_avatar.url
            if ctx.guild
            else self.bot.user.display_avatar.url
        )

        commit_hash = await self.get_commit_hash()
        command_num = len(self.bot.application_commands) + len(
            self.bot.prefixed_commands
        )
        premium_count = await models.GuildConfig.filter(
            premium_code__id__not_isnull=True
        ).count()

        about_embed.add_field(
            name="Stats",
            value="\n".join(
                (
                    f"Servers: {len(self.bot.guilds)}",
                    f"Premium Servers: {premium_count}",
                    f"Commands: {command_num} ",
                    (
                        "Startup Time:"
                        f" {naff.Timestamp.fromdatetime(self.bot.start_time).format(naff.TimestampStyles.RelativeTime)}"
                    ),
                    (
                        "Commit Hash:"
                        f" [{commit_hash}](https://github.com/AstreaTSS/RealmsPlayerlistBot/commit/{commit_hash})"
                    ),
                    (
                        "NAFF Version:"
                        f" [{naff.const.__version__}](https://github.com/NAFTeam/NAFF/tree/NAFF-{naff.const.__version__})"
                    ),
                    "Made By: [AstreaTSS](https://github.com/AstreaTSS)",
                )
            ),
            inline=True,
        )

        links = [
            "Support Server: [Link](https://discord.gg/NSdetwGjpK)",
            "Source Code: [Link](https://github.com/AstreaTSS/RealmsPlayerlistBot)",
        ]

        if os.environ.get("TOP_GG_TOKEN"):
            links.append(f"Top.gg Page: [Link](https://top.gg/bot/{self.bot.user.id})")

        links.extend(
            (
                f"Premium Information: [Link]({os.environ['PREMIUM_INFO_LINK']})",
                (
                    "FAQ: [Link](https://github.com/AstreaTSS/RealmsPlayerlistBot/wiki/FAQ)"
                ),
                (
                    "Privacy Policy:"
                    " [Link](https://github.com/AstreaTSS/RealmsPlayerlistBot/wiki/Privacy-Policy)"
                ),
                (
                    "Terms of Service:"
                    " [Link](https://github.com/AstreaTSS/RealmsPlayerlistBot/wiki/Terms-of-Service)"
                ),
            )
        )

        about_embed.add_field(
            name="Links:",
            value="\n".join(links),
            inline=True,
        )
        about_embed.timestamp = naff.Timestamp.utcnow()

        await ctx.send(embed=about_embed)

    @tansy.slash_command(
        "gamertag-from-xuid",
        description="Gets the gamertag for a specified XUID.",
    )
    async def gamertag_from_xuid(
        self,
        ctx: utils.RealmContext,
        xuid: str = tansy.Option("The XUID of the player to get."),
    ):
        """
        Gets the gamertag for a specified XUID.

        Think of XUIDs as Discord user IDs but for Xbox Live - \
        they are frequently used both in Minecraft and with this bot.
        Gamertags are like the user's username in a sense.

        For technical reasons, when using the playerlist, the bot has to do a XUID > gamertag lookup.
        This lookup usually works well, but on the rare occasion it does fail, the bot will show \
        the XUID of a player instead of their gamertag to at least make sure something is shown about them.

        This command is useful if the bot fails that lookup and displays the XUID to you. This is a reliable \
        way of getting the gamertag, provided the XUID provided is correct in the first place.
        """

        try:
            if len(xuid) > 64:
                raise ValueError()
            valid_xuid = int(xuid)
        except ValueError:
            raise naff.errors.BadArgument(f'"{xuid}" is not a valid XUID.') from None

        maybe_gamertag: typing.Union[
            str, xbox_api.ProfileResponse, None
        ] = await self.bot.redis.get(str(valid_xuid))

        if not maybe_gamertag:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=2.5)
            ) as session:
                headers = {
                    "X-Authorization": os.environ["OPENXBL_KEY"],
                    "Accept": "application/json",
                    "Accept-Language": "en-US",
                }
                with contextlib.suppress(asyncio.TimeoutError):
                    async with session.get(
                        f"https://xbl.io/api/v2/account/{valid_xuid}",
                        headers=headers,
                    ) as r:
                        with contextlib.suppress(
                            ValidationError, aiohttp.ContentTypeError
                        ):
                            maybe_gamertag = xbox_api.parse_profile_response(
                                await r.json(loads=orjson.loads)
                            )

                if not maybe_gamertag:
                    with contextlib.suppress(
                        aiohttp.ClientResponseError,
                        asyncio.TimeoutError,
                        ValidationError,
                        MicrosoftAPIException,
                    ):
                        resp = await self.bot.xbox.fetch_profile_by_xuid(valid_xuid)
                        maybe_gamertag = xbox_api.parse_profile_response(resp)

                if not maybe_gamertag:
                    with contextlib.suppress(asyncio.TimeoutError):
                        async with session.get(
                            f"https://xbl-api.prouser123.me/profile/xuid/{valid_xuid}"
                        ) as r:
                            with contextlib.suppress(
                                ValidationError, aiohttp.ContentTypeError
                            ):
                                maybe_gamertag = xbox_api.parse_profile_response(
                                    await r.json(loads=orjson.loads)
                                )

        if not maybe_gamertag:
            raise naff.errors.BadArgument(
                f"Could not find gamertag of XUID `{valid_xuid}`!"
            )

        if isinstance(maybe_gamertag, xbox_api.ProfileResponse):
            maybe_gamertag = next(
                s.value
                for s in maybe_gamertag.profile_users[0].settings
                if s.id == "Gamertag"
            )

            await self.bot.redis.setex(
                name=str(valid_xuid),
                time=datetime.timedelta(days=14),
                value=maybe_gamertag,
            )

        await ctx.send(f"`{valid_xuid}`'s gamertag: `{maybe_gamertag}`.")


def setup(bot):
    importlib.reload(utils)
    importlib.reload(xbox_api)
    GeneralCMDS(bot)
