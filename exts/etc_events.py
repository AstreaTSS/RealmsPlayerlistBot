#!/usr/bin/env python3.8
import importlib

import naff

import common.utils as utils
from common.models import GuildConfig


class OnCMDError(naff.Extension):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot

    @naff.listen("guild_join")
    async def on_guild_join(self, event: naff.events.GuildJoin):
        if not self.bot.is_ready:
            return

        exists = await GuildConfig.exists(guild_id=event.guild.id)
        if not exists:
            await GuildConfig.create(
                guild_id=event.guild.id,
                prefixes={"!?"},
            )

    @naff.listen("guild_left")
    async def on_guild_left(self, event: naff.events.GuildLeft):
        if not self.bot.is_ready:
            return

        await GuildConfig.filter(guild_id=int(event.guild_id)).delete()


def setup(bot):
    importlib.reload(utils)
    OnCMDError(bot)
