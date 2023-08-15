import asyncio
import contextlib
import importlib
import os
import subprocess
import time
import typing

import aiohttp
import elytra
import interactions as ipy
import tansy
from msgspec import ValidationError
from tortoise.expressions import Q

import common.models as models
import common.utils as utils


class GeneralCMDS(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.name = "General"
        self.bot: utils.RealmBotBase = bot

        self.invite_link = ""
        self.bot.create_task(self.async_wait())

    async def async_wait(self) -> None:
        await self.bot.wait_until_ready()
        self.invite_link = f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=309238025280&scope=applications.commands%20bot"

    def _get_commit_hash(self) -> str:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .decode("ascii")
            .strip()
        )

    async def get_commit_hash(self) -> str:
        return await asyncio.to_thread(self._get_commit_hash)

    @ipy.slash_command(
        "ping",
        description=(
            "Pings the bot. Great way of finding out if the bot's working correctly,"
            " but has no real use."
        ),
    )
    async def ping(self, ctx: utils.RealmContext) -> None:
        """
        Pings the bot. Great way of finding out if the bot's working correctly, but has no real use.
        """

        start_time = time.perf_counter()
        average_ping = round((self.bot.latency * 1000), 2)
        shard_id = self.bot.get_shard_id(ctx.guild_id) if ctx.guild_id else 0
        shard_ping = round((self.bot.latencies[shard_id] * 1000), 2)

        embed = ipy.Embed(
            "Pong!", color=self.bot.color, timestamp=ipy.Timestamp.utcnow()
        )
        embed.set_footer(f"Shard ID: {shard_id}")
        embed.description = (
            f"Average Ping: `{average_ping}` ms\nShard Ping: `{shard_ping}`"
            " ms\nCalculating RTT..."
        )

        await ctx.send(embed=embed)

        end_time = time.perf_counter()
        # not really rtt ping but shh
        rtt_ping = round(((end_time - start_time) * 1000), 2)
        embed.description = (
            f"Average Ping: `{average_ping}` ms\nShard Ping: `{shard_ping}` ms\nRTT"
            f" Ping: `{rtt_ping}` ms"
        )

        await ctx.edit(embed=embed)

    @ipy.slash_command(
        name="invite",
        description="Sends instructions on how to set up and invite the bot.",
    )
    async def invite(self, ctx: utils.RealmContext) -> None:
        embed = utils.make_embed(
            "If you want to invite me to your server, it's a good idea to use the"
            " Server Setup Guide. However, if you know what you're doing, you can"
            " use the Invite Link instead.",
            title="Invite Bot",
        )
        components = [
            ipy.Button(
                style=ipy.ButtonStyle.URL,
                label="Server Setup Guide",
                url=os.environ["SETUP_LINK"],
            ),
            ipy.Button(
                style=ipy.ButtonStyle.URL,
                label="Invite Link",
                url=self.invite_link,
            ),
        ]
        await ctx.send(embeds=embed, components=components)

    @ipy.slash_command(
        "support", description="Gives an invite link to the support server."
    )
    async def support(self, ctx: ipy.InteractionContext) -> None:
        embed = utils.make_embed(
            "If you need help with the bot, or just want to hang out, join the"
            " support server!",
            title="Support Server",
        )
        button = ipy.Button(
            style=ipy.ButtonStyle.URL,
            label="Join Support Server",
            url="https://discord.gg/NSdetwGjpK",
        )
        await ctx.send(embeds=embed, components=button)

    @ipy.slash_command("about", description="Gives information about the bot.")
    async def about(self, ctx: ipy.InteractionContext) -> None:
        msg_list = [
            (
                "Hi! I'm the **Realms Playerlist Bot**, a bot that helps out owners of"
                " Minecraft: Bedrock Edition Realms by showing a log of players who"
                " have joined and left."
            ),
            (
                "If you want to use me, go ahead and invite me to your server and take"
                f" a look at {self.bot.mention_cmd('config help')}!"
            ),
            (
                "*The Realms Playerlist Bot is not an official Minecraft product, and"
                " is not approved by or associated with Mojang or Microsoft.*"
            ),
        ]

        about_embed = ipy.Embed(
            title="About",
            color=self.bot.color,
            description="\n".join(msg_list),
        )
        about_embed.set_thumbnail(
            ctx.bot.user.display_avatar.url
            if ctx.guild
            else self.bot.user.display_avatar.url
        )

        commit_hash = await self.get_commit_hash()
        command_num = len(self.bot.application_commands) + len(
            self.bot.prefixed.commands
        )
        premium_count = await models.GuildConfig.filter(
            Q(premium_code__id__not_isnull=True)
            & Q(
                Q(premium_code__expires_at__isnull=True)
                | Q(premium_code__expires_at__gt=ctx.id.created_at)
            )
        ).count()

        num_shards = len(self.bot.shards)
        shards_str = f"{num_shards} shards" if num_shards != 1 else "1 shard"

        about_embed.add_field(
            name="Stats",
            value="\n".join(
                (
                    f"Servers: {len(self.bot.guilds)} ({shards_str})",
                    f"Premium Servers: {premium_count}",
                    f"Commands: {command_num} ",
                    (
                        "Startup Time:"
                        f" {ipy.Timestamp.fromdatetime(self.bot.start_time).format(ipy.TimestampStyles.RelativeTime)}"
                    ),
                    (
                        "Commit Hash:"
                        f" [{commit_hash}](https://github.com/AstreaTSS/RealmsPlayerlistBot/commit/{commit_hash})"
                    ),
                    (
                        "Interactions.py Version:"
                        f" [{ipy.__version__}](https://github.com/interactions-py/interactions.py/tree/{ipy.__version__})"
                    ),
                    "Made By: [AstreaTSS](https://astrea.cc)",
                )
            ),
            inline=True,
        )

        links = [
            "Website: [Link](https://rpl.astrea.cc)",
            "FAQ: [Link](https://rpl.astrea.cc/wiki/faq.html)",
            "Support Server: [Link](https://discord.gg/NSdetwGjpK)",
        ]

        if os.environ.get("TOP_GG_TOKEN"):
            links.append(f"Top.gg Page: [Link](https://top.gg/bot/{self.bot.user.id})")

        links.extend(
            (
                "Source Code: [Link](https://github.com/AstreaTSS/RealmsPlayerlistBot)",
                (
                    "Privacy Policy:"
                    " [Link](https://rpl.astrea.cc/legal/privacy_policy.html)"
                ),
                "Terms of Service: [Link](https://rpl.astrea.cc/legal/tos.html)",
            )
        )

        about_embed.add_field(
            name="Links",
            value="\n".join(links),
            inline=True,
        )
        about_embed.timestamp = ipy.Timestamp.utcnow()

        shard_id = self.bot.get_shard_id(ctx.guild_id) if ctx.guild_id else 0
        about_embed.set_footer(f"Shard ID: {shard_id}")

        await ctx.send(embed=about_embed)

    @tansy.slash_command(
        "gamertag-from-xuid",
        description="Gets the gamertag for a specified XUID.",
        dm_permission=False,
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    async def gamertag_from_xuid(
        self,
        ctx: utils.RealmContext,
        xuid: str = tansy.Option("The XUID of the player to get."),
    ) -> None:
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
            raise ipy.errors.BadArgument(f'"{xuid}" is not a valid XUID.') from None

        maybe_gamertag: typing.Union[str, elytra.ProfileResponse, None] = (
            await self.bot.redis.get(str(valid_xuid))
        )

        if not maybe_gamertag:
            with contextlib.suppress(asyncio.TimeoutError):
                async with self.bot.openxbl_session.get(
                    f"https://xbl.io/api/v2/account/{valid_xuid}",
                    timeout=10,
                ) as r:
                    with contextlib.suppress(ValidationError, aiohttp.ContentTypeError):
                        maybe_gamertag = await elytra.ProfileResponse.from_response(r)

        if not maybe_gamertag:
            with contextlib.suppress(
                aiohttp.ClientResponseError,
                asyncio.TimeoutError,
                ValidationError,
                elytra.MicrosoftAPIException,
            ):
                maybe_gamertag = await self.bot.xbox.fetch_profile_by_xuid(valid_xuid)

        if not maybe_gamertag:
            raise ipy.errors.BadArgument(
                f"Could not find gamertag of XUID `{valid_xuid}`!"
            )

        if isinstance(maybe_gamertag, elytra.ProfileResponse):
            maybe_gamertag = next(
                s.value
                for s in maybe_gamertag.profile_users[0].settings
                if s.id == "Gamertag"
            )

            async with self.bot.redis.pipeline() as pipe:
                pipe.setex(
                    name=str(valid_xuid),
                    time=utils.EXPIRE_GAMERTAGS_AT,
                    value=maybe_gamertag,
                )
                pipe.setex(
                    name=f"rpl-{maybe_gamertag}",
                    time=utils.EXPIRE_GAMERTAGS_AT,
                    value=str(valid_xuid),
                )
                await pipe.execute()

        embed = utils.make_embed(
            f"`{valid_xuid}`'s gamertag: `{maybe_gamertag}`.",
            title="Gamertag from XUID",
        )
        await ctx.send(embed=embed)


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    GeneralCMDS(bot)
