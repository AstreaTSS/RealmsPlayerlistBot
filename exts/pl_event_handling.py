import contextlib
import importlib
import logging
import os

import naff

import common.models as models
import common.playerlist_events as pl_events
import common.playerlist_utils as pl_utils
import common.utils as utils
from common.microsoft_core import MicrosoftAPIException


class PlayerlistEventHandling(naff.Extension):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.name = "Playerlist Event Handling"

    @naff.listen("playerlist_parse_finish", is_default_listener=True)
    async def on_playerlist_finish(self, event: pl_events.PlayerlistParseFinish):
        for container in event.containers:
            await models.RealmPlayer.bulk_create(
                container.realmplayers,
                on_conflict=("realm_xuid_id",),
                update_fields=container.fields,
            )

    @naff.listen("live_playerlist_send", is_default_listener=True)
    async def on_live_playerlist_send(self, event: pl_events.LivePlayerlistSend):
        realmplayers = [
            models.RealmPlayer(
                realm_xuid_id=f"{event.realm_id}-{p}",
                online=True,
                last_seen=event.last_seen,
            )
            for p in event.joined.union(event.left)
        ]
        players = await pl_utils.get_players_from_realmplayers(
            self.bot, event.realm_id, realmplayers
        )
        gamertag_mapping = {p.xuid: p.base_display for p in players}

        embed = naff.Embed(
            color=self.bot.color,
            timestamp=naff.Timestamp.fromdatetime(event.last_seen),
        )
        embed.set_footer(
            f"{len(self.bot.online_cache[int(event.realm_id)])} players online as of"
        )

        if event.joined:
            embed.add_field(
                name=f"{os.environ['GREEN_CIRCLE_EMOJI']} Joined",
                value="\n".join(gamertag_mapping[p] for p in event.joined),
            )
        if event.left:
            embed.add_field(
                name=f"{os.environ['GRAY_CIRCLE_EMOJI']} Left",
                value="\n".join(gamertag_mapping[p] for p in event.left),
            )

        for guild_id in self.bot.live_playerlist_store[event.realm_id].copy():
            config = await models.GuildConfig.get(guild_id=guild_id).prefetch_related(
                "premium_code"
            )

            if not config.premium_code or not config.playerlist_chan:
                self.bot.live_playerlist_store[event.realm_id].discard(guild_id)
                continue

            guild = self.bot.get_guild(guild_id)
            if not guild:
                # could just be it's offline or something
                continue

            try:
                chan = await pl_utils.fetch_playerlist_channel(self.bot, guild, config)
                await chan.send(embeds=embed)
            except ValueError:
                continue
            except naff.errors.HTTPException:
                await pl_utils.eventually_invalidate(self.bot, config)
                continue

    @naff.listen("realm_down", is_default_listener=True)
    async def realm_down(self, event: pl_events.RealmDown):
        if self.bot.live_playerlist_store[event.realm_id]:
            self.bot.dispatch(
                pl_events.LivePlayerlistSend(
                    event.realm_id, set(), event.disconnected, event.last_seen
                )
            )

    @naff.listen("warn_missing_playerlist", is_default_listener=True)
    async def warning_missing_playerlist(self, event: pl_events.WarnMissingPlayerlist):
        no_playerlist_chan: list[bool] = []

        async for config in event.configs:
            if not config.playerlist_chan:
                config.realm_id = None
                config.club_id = None
                await config.save()

                no_playerlist_chan.append(True)
                continue

            no_playerlist_chan.append(False)

            guild = self.bot.get_guild(config.guild_id)
            if not guild:
                # could just be it's offline or something
                continue

            try:
                chan = await pl_utils.fetch_playerlist_channel(self.bot, guild, config)
            except ValueError:
                continue

            with contextlib.suppress(naff.errors.HTTPException):
                embed = naff.Embed(
                    title="Warning",
                    description=(
                        "I have been unable to get any information about your"
                        " Realm for the last 24 hours. This could be because the"
                        " Realm has been turned off or because it's inactive, but"
                        " if it hasn't, make sure you haven't banned or kick"
                        f" `{self.bot.own_gamertag}`. If you have, please unban the"
                        " account if needed and run `/config link-realm` again to"
                        " fix it.\n\nAlternatively, if you want to disable the"
                        " autorunner entirely, you can use `/config"
                        " unset-playerlist-channel` to do so."
                    ),
                    color=naff.RoleColors.YELLOW,
                )
                await chan.send(embeds=embed)

            await pl_utils.eventually_invalidate(self.bot, config, limit=7)

        if all(no_playerlist_chan) or not no_playerlist_chan:
            # we don't want to stop the whole thing, but as of right now i would
            # like to know what happens with invalid stuff
            try:
                await self.bot.realms.leave_realm(event.realm_id)
            except MicrosoftAPIException as e:
                # might be an invalid id somehow? who knows
                if e.resp.status == 404:
                    logging.getLogger("realms_bot").warning(
                        f"Could not leave Realm with ID {event.realm_id}."
                    )
                    return
                raise

        self.bot.offline_realm_time.pop(int(event.realm_id), None)


def setup(bot):
    importlib.reload(utils)
    importlib.reload(pl_events)
    importlib.reload(pl_utils)
    PlayerlistEventHandling(bot)
