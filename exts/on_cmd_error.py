import datetime
import importlib

import humanize
import naff

import common.utils as utils


class OnCMDError(naff.Extension):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.bot.on_command_error = self.on_command_error

    def error_embed_generate(self, error_msg):
        return naff.Embed(color=naff.MaterialColors.RED, description=error_msg)

    async def on_command_error(
        self, ctx: naff.Context, error: Exception, *args, **kwargs
    ):
        if not ctx.bot.is_ready or not isinstance(
            ctx, (utils.RealmContext, utils.RealmPrefixedContext)
        ):
            return

        if isinstance(error, naff.errors.CommandOnCooldown):
            delta_wait = datetime.timedelta(seconds=error.cooldown.get_cooldown_time())
            await ctx.send(
                embeds=self.error_embed_generate(
                    "You're doing that command too fast! "
                    + "Try again in"
                    f" `{humanize.precisedelta(delta_wait, format='%0.0f')}`."
                )
            )
        elif isinstance(
            error,
            naff.errors.BadArgument,
        ):
            await ctx.send(embeds=self.error_embed_generate(str(error)))
        elif isinstance(error, utils.CustomCheckFailure):
            await ctx.send(embeds=self.error_embed_generate(str(error)))
        elif isinstance(error, naff.errors.CommandCheckFailure):
            if ctx.guild:
                await ctx.send(
                    embeds=self.error_embed_generate(
                        "You do not have the proper permissions to use that command."
                    )
                )
        else:
            await utils.error_handle(self.bot, error, ctx)


def setup(bot):
    importlib.reload(utils)
    OnCMDError(bot)
