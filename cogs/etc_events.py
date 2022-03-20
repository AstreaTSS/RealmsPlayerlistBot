#!/usr/bin/env python3.8
import datetime
import importlib

import humanize
import nextcord
from nextcord.ext import commands

import common.utils as utils
from common.models import GuildConfig


class OnCMDError(commands.Cog):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: nextcord.Guild):
        exists = await GuildConfig.exists(guild_id=guild.id)
        if not exists:
            await GuildConfig.create(
                guild_id=guild.id,
                prefixes={"!?"},
            )
            self.bot.cached_prefixes[guild.id] = {"!?"}

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: nextcord.Guild):
        await GuildConfig.filter(guild_id=guild.id).delete()
        self.bot.cached_prefixes.pop(guild.id)

    def error_embed_generate(self, error_msg):
        return nextcord.Embed(colour=nextcord.Colour.red(), description=error_msg)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        # sourcery skip: remove-pass-elif
        if not ctx.bot.is_ready():
            return

        if isinstance(error, commands.CommandInvokeError):
            await utils.error_handle(self.bot, error, ctx)
        elif isinstance(error, commands.DisabledCommand):
            await ctx.reply(
                embed=self.error_embed_generate(
                    (
                        f"{error}. This was most likely due to "
                        + "it being buggy or broken in some way - please wait for it to"
                        " be re-enabled."
                    )
                )
            )

        elif isinstance(error, commands.TooManyArguments):
            await ctx.reply(
                embed=self.error_embed_generate(
                    "You passed too many arguments to that command! Please make sure"
                    " you're "
                    + "passing in a valid argument/subcommand."
                )
            )
        elif isinstance(error, commands.CommandOnCooldown):
            delta_wait = datetime.timedelta(seconds=error.retry_after)
            await ctx.reply(
                embed=self.error_embed_generate(
                    "You're doing that command too fast! "
                    + "Try again in"
                    f" `{humanize.precisedelta(delta_wait, format='%0.0f')}`."
                )
            )
        elif isinstance(
            error,
            (commands.ConversionError, commands.UserInputError, commands.BadArgument),
        ):
            await ctx.reply(embed=self.error_embed_generate(str(error)))
        elif isinstance(error, utils.CustomCheckFailure):
            await ctx.reply(embed=self.error_embed_generate(str(error)))
        elif isinstance(error, commands.CheckFailure):
            if ctx.guild:
                await ctx.reply(
                    embed=self.error_embed_generate(
                        "You do not have the proper permissions to use that command."
                    )
                )
        elif isinstance(error, commands.CommandNotFound):
            pass
        else:
            await utils.error_handle(self.bot, error, ctx)


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(OnCMDError(bot))
