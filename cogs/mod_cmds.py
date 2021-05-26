import asyncio
import datetime
import importlib
import os
import urllib.parse

import aiohttp
import discord
from discord.ext import commands

import common.utils as utils


class ModCMDS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def verify_xbl_handler(self, gamertag):
        mem_gt_url = urllib.parse.quote_plus(gamertag.strip())

        headers = {
            "X-Authorization": os.environ.get("OPENXBL_KEY"),
            "Accept": "application/json",
            "Accept-Language": "en-US",
        }

        mem_gt_url = mem_gt_url.replace("%27", "")

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                "https://xbl.io/api/v2/friends/search", params=f"gt={mem_gt_url}"
            ) as r:
                try:
                    resp_json = await r.json()
                except:
                    return f"ERROR: Unable to find the gamertag `{gamertag}`."

                if "code" in resp_json.keys():
                    return f"ERROR: Unable to find the gamertag `{gamertag}`."
                settings = {
                    setting["id"]: setting["value"]
                    for setting in resp_json["profileUsers"][0]["settings"]
                }

                if settings["XboxOneRep"] != "GoodPlayer":
                    return (
                        f"WARNING: The gamertag `{gamertag}` exists, but doesn't have the best reputation on Xbox Live.\n"
                        + "Reputation is a measure of how trustworthy a user is in online play, so be careful."
                    )
                elif settings["Gamerscore"] == "0":
                    return f"WARNING: The gamertag `{gamertag}` exists, but has no gamerscore. This is probably a new user, so be careful."
                else:
                    return "OK"

    @commands.command()
    @utils.proper_permissions()
    async def season_add(self, ctx, season, message_id=None):
        timestamp = datetime.datetime.utcnow().timestamp()
        guild_entry = self.bot.config[str(ctx.guild.id)]

        if message_id != None:
            try:
                announce_chan = guild_entry["announce_chan"]
                ori_mess = await ctx.guild.get_channel(announce_chan).fetch_message(
                    int(message_id)
                )
                timestamp = ori_mess.created_at.timestamp()
            except discord.NotFound:
                await ctx.send(
                    "Invalid message ID! Make sure the message is in the announcements channel for this server."
                )
                return

        guild_members = ctx.guild.members

        season_x_role = discord.utils.get(
            ctx.guild.roles, name=guild_entry["season_role"].replace("X", season)
        )
        if season_x_role is None:
            await ctx.send("Invalid season number!")
        else:
            season_x_vets = [
                member
                for member in guild_members
                if member.joined_at.timestamp() < timestamp
                and not member.bot
                and season_x_role not in member.roles
            ]

            for vet in season_x_vets:
                await vet.add_roles(season_x_role)
                await asyncio.sleep(1)

            await ctx.send("Done! Added " + str(len(season_x_vets)) + " members!")

    @commands.command(aliases=["gtcheck"])
    @utils.proper_permissions()
    async def gt_check(self, ctx, *, gamertag):
        async with ctx.channel.typing():
            status = await self.verify_xbl_handler(gamertag)

            if status != "OK":
                await ctx.send(f"{status}")
            else:
                await ctx.send(f"The gamertag `{gamertag}` has passed all checks.")


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(ModCMDS(bot))
