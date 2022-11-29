import asyncio
import importlib
import os

import naff

import common.utils as utils
from common.models import GuildConfig


class OnCMDError(naff.Extension):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.update_tokens.start()

    def drop(self):
        self.update_tokens.stop()
        super().drop()

    @naff.listen("guild_join")
    async def on_guild_join(self, event: naff.events.GuildJoin):
        if not self.bot.is_ready:
            return

        exists = await GuildConfig.exists(guild_id=int(event.guild_id))
        if not exists:
            await GuildConfig.create(
                guild_id=int(event.guild_id),
            )

    @naff.listen("guild_left")
    async def on_guild_left(self, event: naff.events.GuildLeft):
        if not self.bot.is_ready:
            return

        await GuildConfig.filter(guild_id=event.guild.id).delete()

    def _update_tokens(self):
        with open(os.environ["XAPI_TOKENS_LOCATION"], mode="w") as f:
            f.write(self.bot.xbox.auth_mgr.oauth.json())

    @naff.Task.create(naff.IntervalTrigger(hours=6))
    async def update_tokens(self):
        await asyncio.to_thread(self._update_tokens)


def setup(bot):
    importlib.reload(utils)
    OnCMDError(bot)
