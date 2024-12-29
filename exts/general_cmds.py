"""
Copyright 2020-2024 AstreaTSS.
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
import importlib
import os
import subprocess
import time

import interactions as ipy
import tansy

import common.classes as cclasses
import common.models as models
import common.playerlist_utils as pl_utils
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

    def _get_commit_hash(self) -> str | None:
        try:
            return (
                subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
                .decode("ascii")
                .strip()
            )
        except Exception:  # screw it
            return None

    async def get_commit_hash(self) -> str | None:
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
                url="https://playerlist.astrea.cc/wiki/server_setup.html",
            ),
            ipy.Button(
                style=ipy.ButtonStyle.URL,
                label="Invite Link",
                url=self.invite_link,
            ),
        ]
        await ctx.send(embeds=embed, components=components)

    @ipy.slash_command(
        "support", description="Gives information about getting support."
    )
    async def support(self, ctx: ipy.InteractionContext) -> None:
        embed = utils.make_embed(
            "Check out the FAQ to see if your question/issue has already been answered."
            " If not, feel free to join the support server and ask your question/report"
            " your issue there.",
            title="Support",
        )

        components = [
            ipy.Button(
                style=ipy.ButtonStyle.URL,
                label="Read the FAQ",
                url="https://playerlist.astrea.cc/wiki/faq.html",
            ),
            ipy.Button(
                style=ipy.ButtonStyle.URL,
                label="Join Support Server",
                url="https://discord.gg/NSdetwGjpK",
            ),
        ]
        await ctx.send(embeds=embed, components=components)

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
                f" a look at {self.bot.mention_command('config help')}!"
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
            if ctx.guild_id
            else self.bot.user.display_avatar.url
        )

        commit_hash = await self.get_commit_hash()
        command_num = len(self.bot.application_commands) + len(
            self.bot.prefixed.commands
        )
        premium_count = await models.GuildConfig.prisma().count(
            where={
                "NOT": [{"premium_code_id": None}],
                "OR": [
                    {"premium_code": {"is_not": {"expires_at": None}}},
                    {"premium_code": {"is": {"expires_at": {"gt": ctx.id.created_at}}}},
                ],
            }
        )

        num_shards = len(self.bot.shards)
        shards_str = f"{num_shards} shards" if num_shards != 1 else "1 shard"

        about_embed.add_field(
            name="Stats",
            value="\n".join(
                (
                    f"Servers: {self.bot.guild_count} ({shards_str})",
                    f"Premium Servers: {premium_count}",
                    f"Commands: {command_num} ",
                    (
                        "Startup Time:"
                        f" {ipy.Timestamp.fromdatetime(self.bot.start_time).format(ipy.TimestampStyles.RelativeTime)}"
                    ),
                    (
                        "Commit Hash:"
                        f" [{commit_hash}](https://github.com/AstreaTSS/RealmsPlayerlistBot/commit/{commit_hash})"
                        if commit_hash
                        else "Commit Hash: N/A"
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
            "Website: [Link](https://playerlist.astrea.cc)",
            "FAQ: [Link](https://playerlist.astrea.cc/wiki/faq.html)",
            "Support Server: [Link](https://discord.gg/NSdetwGjpK)",
        ]

        if os.environ.get("TOP_GG_TOKEN"):
            links.append(f"Top.gg Page: [Link](https://top.gg/bot/{self.bot.user.id})")

        links.extend(
            (
                "Source Code: [Link](https://github.com/AstreaTSS/RealmsPlayerlistBot)",
                (
                    "Privacy Policy:"
                    " [Link](https://playerlist.astrea.cc/legal/privacy_policy.html)"
                ),
                "Terms of Service: [Link](https://playerlist.astrea.cc/legal/tos.html)",
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

        This command is useful if the bot fails that lookup and displays the XUID to you.
        """

        try:
            if len(xuid) > 64:
                raise ValueError()

            valid_xuid = int(xuid) if xuid.isdigit() else int(xuid, 16)
        except ValueError:
            raise ipy.errors.BadArgument(f'"{xuid}" is not a valid XUID.') from None

        gamertag = await pl_utils.gamertag_from_xuid(self.bot, valid_xuid)
        embed = utils.make_embed(
            f"`{valid_xuid}`'s gamertag: `{gamertag}`.",
            title="Gamertag from XUID",
        )
        await ctx.send(embed=embed)

    @tansy.slash_command(
        "xuid-from-gamertag",
        description="Gets the XUID for a specified gamertag.",
        dm_permission=False,
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    async def xuid_from_gamertag(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the player to get."),
    ) -> None:
        xuid = await pl_utils.xuid_from_gamertag(self.bot, gamertag)
        embed = utils.make_embed(
            f"`{gamertag}`'s XUID: `{xuid}` (hex: `{int(xuid):0{len(xuid)}X}`).",
            title="XUID from gamertag",
        )
        await ctx.send(embed=embed)


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(pl_utils)
    importlib.reload(cclasses)
    GeneralCMDS(bot)
