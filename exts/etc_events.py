import asyncio
import contextlib
import importlib
import os

import naff

import common.models as models
import common.utils as utils
from common.microsoft_core import MicrosoftAPIException


class OnCMDError(naff.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.update_tokens.start()

    def drop(self) -> None:
        self.update_tokens.stop()
        super().drop()

    @naff.listen("guild_join")
    async def on_guild_join(self, event: naff.events.GuildJoin) -> None:
        if not self.bot.is_ready:
            return

        await models.GuildConfig.get_or_create(guild_id=int(event.guild_id))

    @naff.listen("guild_left")
    async def on_guild_left(self, event: naff.events.GuildLeft) -> None:
        if not self.bot.is_ready:
            return

        if config := await models.GuildConfig.get_or_none(guild_id=int(event.guild.id)):
            if (
                config.realm_id
                and await models.GuildConfig.filter(
                    guild_id__not=int(event.guild.id)
                ).count()
                == 0
            ):
                # don't want to keep around entries we no longer need, so delete them
                await models.PlayerSession.filter(
                    realm_xuid_id__startswith=f"{config.realm_id}-"
                ).delete()
                # also attempt to leave the realm cus why not
                with contextlib.suppress(MicrosoftAPIException):
                    await self.bot.realms.leave_realm(config.realm_id)
            await config.delete()

    def _update_tokens(self) -> None:
        with open(os.environ["XAPI_TOKENS_LOCATION"], mode="w") as f:
            f.write(self.bot.xbox.auth_mgr.oauth.json())

    @naff.Task.create(naff.IntervalTrigger(hours=6))
    async def update_tokens(self) -> None:
        await asyncio.to_thread(self._update_tokens)


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    OnCMDError(bot)
