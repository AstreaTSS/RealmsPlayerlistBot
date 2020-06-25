from discord.ext import commands
import urllib.parse, aiohttp, os, discord, datetime
import cogs.universals as univ

class ModCMDS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.check(univ.proper_permissions)
    async def season_add(self, ctx, season, message_id = None):
        timestamp = datetime.datetime.utcnow().timestamp()
        guild_entry = self.bot.config[str(ctx.guild.id)]

        if message_id != None:
            try:
                announce_chan = guild_entry["announce_chan"]
                ori_mess = await ctx.guild.get_channel(announce_chan).fetch_message(int(message_id))
                timestamp = ori_mess.created_at.timestamp()
            except discord.NotFound:
                await ctx.send("Invalid message ID! Make sure the message is in the announcements channel for this server.")
                return
        
        guild_members = ctx.guild.members

        season_x_role = discord.utils.get(ctx.guild.roles, name=guild_entry["season_role"].replace("X", season))
        if season_x_role == None:
            await ctx.send("Invalid season number!")
        else:
            season_x_vets = []

            for member in guild_members:
                if member.joined_at.timestamp() < timestamp and not member.bot and not season_x_role in member.roles:
                    season_x_vets.append(member)

            for vet in season_x_vets:
                await vet.add_roles(season_x_role)

            await ctx.send("Done! Added " + str(len(season_x_vets)) + " members!")

def setup(bot):
    bot.add_cog(ModCMDS(bot))
