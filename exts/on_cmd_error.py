import datetime
import importlib

import humanize
import naff

import common.utils as utils


class OnCMDError(naff.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot

    def error_embed_generate(self, error_msg: str) -> naff.Embed:
        return naff.Embed(color=naff.MaterialColors.RED, description=error_msg)

    @naff.listen(disable_default_listeners=True)
    async def on_command_error(
        self,
        event: naff.events.CommandError,
    ) -> None:
        if not isinstance(event.ctx, (naff.PrefixedContext, naff.InteractionContext)):
            return await utils.error_handle(event.error)

        if isinstance(event.error, naff.errors.CommandOnCooldown):
            delta_wait = datetime.timedelta(
                seconds=event.error.cooldown.get_cooldown_time()
            )
            await event.ctx.send(
                embeds=self.error_embed_generate(
                    "You're doing that command too fast! "
                    + "Try again in"
                    f" `{humanize.precisedelta(delta_wait, format='%0.0f')}`."
                )
            )
        elif isinstance(
            event.error, (utils.CustomCheckFailure, naff.errors.BadArgument)
        ):
            await event.ctx.send(embeds=self.error_embed_generate(str(event.error)))
        elif isinstance(event.error, naff.errors.CommandCheckFailure):
            if event.ctx.guild:
                await event.ctx.send(
                    embeds=self.error_embed_generate(
                        "You do not have the proper permissions to use that command."
                    )
                )
        else:
            await utils.error_handle(event.error, ctx=event.ctx)


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    OnCMDError(bot)
