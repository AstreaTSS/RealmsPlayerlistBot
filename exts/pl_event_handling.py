import contextlib
import importlib
import logging
import os
import typing

import interactions as ipy

import common.models as models
import common.playerlist_events as pl_events
import common.playerlist_utils as pl_utils
import common.utils as utils
from common.microsoft_core import MicrosoftAPIException


class PlayerlistEventHandling(ipy.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.name = "Playerlist Event Handling"

    @ipy.listen("playerlist_parse_finish", is_default_listener=True)
    async def on_playerlist_finish(
        self, event: pl_events.PlayerlistParseFinish
    ) -> None:
        for container in event.containers:
            await models.PlayerSession.bulk_create(
                container.player_sessions,
                on_conflict=("custom_id",),
                update_fields=container.fields,
            )

    @ipy.listen("live_playerlist_send", is_default_listener=True)
    async def on_live_playerlist_send(
        self, event: pl_events.LivePlayerlistSend
    ) -> None:
        player_sessions = [
            models.PlayerSession(
                custom_id=self.bot.uuid_cache[f"{event.realm_id}-{p}"],
                realm_id=event.realm_id,
                xuid=p,
                online=True,
                joined_at=event.timestamp,
            )
            for p in event.joined
        ]
        player_sessions.extend(
            models.PlayerSession(
                custom_id=self.bot.uuid_cache[f"{event.realm_id}-{p}"],
                realm_id=event.realm_id,
                xuid=p,
                online=False,
                last_seen=event.timestamp,
                show_left=False,
            )
            for p in event.left
        )

        bypass_cache_for = set()
        if event.realm_id in self.bot.fetch_devices_for:
            bypass_cache_for.update(p.xuid for p in player_sessions if p.online)

        players = await pl_utils.fill_in_gamertags_for_sessions(
            self.bot,
            player_sessions,
            bypass_cache_for=bypass_cache_for,
        )
        gamertag_mapping = {p.xuid: p.base_display for p in players}
        full_gamertag_mapping = {p.xuid: p.display for p in players}

        embed = ipy.Embed(
            color=ipy.RoleColors.DARK_GREY,
            timestamp=ipy.Timestamp.fromdatetime(event.timestamp),
        )
        embed.set_footer(
            f"{len(self.bot.online_cache[int(event.realm_id)])} players online as of"
        )

        if event.joined:
            embed.add_field(
                name=f"{os.environ['GREEN_CIRCLE_EMOJI']} Joined",
                value="\n".join(
                    sorted(
                        (gamertag_mapping[p] for p in event.joined),
                        key=lambda x: x.lower(),
                    )
                ),
            )
        if event.left:
            embed.add_field(
                name=f"{os.environ['GRAY_CIRCLE_EMOJI']} Left",
                value="\n".join(
                    sorted(
                        (gamertag_mapping[p] for p in event.left),
                        key=lambda x: x.lower(),
                    )
                ),
            )

        for guild_id in self.bot.live_playerlist_store[event.realm_id].copy():
            config = await models.GuildConfig.get_or_none(
                guild_id=guild_id
            ).prefetch_related("premium_code")

            if not config:
                self.bot.live_playerlist_store[event.realm_id].discard(guild_id)
                continue

            if not config.premium_code:
                await pl_utils.invalidate_premium(self.bot, config)
                continue

            if not config.live_playerlist:
                self.bot.live_playerlist_store[event.realm_id].discard(guild_id)
                continue

            if not config.playerlist_chan:
                config.live_playerlist = False
                self.bot.live_playerlist_store[event.realm_id].discard(guild_id)
                await config.save()
                continue

            guild = self.bot.get_guild(guild_id)
            if not guild:
                # could just be it's offline or something
                continue

            if config.live_online_channel:
                self.bot.dispatch(
                    pl_events.LiveOnlineUpdate(
                        event.realm_id,
                        event.joined,
                        event.left,
                        event.timestamp,
                        full_gamertag_mapping,
                        config,
                    )
                )

            try:
                chan = await pl_utils.fetch_playerlist_channel(self.bot, guild, config)
                await chan.send(embeds=embed)
            except ValueError:
                continue
            except ipy.errors.HTTPException:
                await pl_utils.eventually_invalidate(self.bot, config)
                continue

    @ipy.listen("live_online_update", is_default_listener=True)
    async def on_live_online_update(self, event: pl_events.LiveOnlineUpdate) -> None:
        xuid_str: str | None = await self.bot.redis.hget(
            event.live_online_channel, "xuids"
        )
        gamertag_str: str | None = await self.bot.redis.hget(
            event.live_online_channel, "gamertags"
        )

        if typing.TYPE_CHECKING:
            # a lie, but a harmless one and one needed to make typehints properly work
            assert isinstance(xuid_str, str)
            assert isinstance(gamertag_str, str)

        xuids_init: list[str] = xuid_str.split(",") if xuid_str else []
        gamertags: list[str] = gamertag_str.splitlines() if gamertag_str else []

        event.gamertag_mapping.update(dict(zip(xuids_init, gamertags, strict=True)))
        reverse_gamertag_map = {v: k for k, v in event.gamertag_mapping.items()}

        xuids: set[str] = set(xuids_init)
        xuids = xuids.union(event.joined).difference(event.left)

        gamertag_list = sorted(
            (event.gamertag_mapping[xuid] for xuid in xuids), key=lambda g: g.lower()
        )
        xuid_list = [reverse_gamertag_map[g] for g in gamertag_list]

        new_gamertag_str = "\n".join(gamertag_list)

        await self.bot.redis.hset(
            event.live_online_channel, "xuids", ",".join(xuid_list)
        )
        await self.bot.redis.hset(
            event.live_online_channel, "gamertags", new_gamertag_str
        )

        embed = ipy.Embed(
            title=f"{len(xuids)}/10 people online",
            description=new_gamertag_str or "*No players online.*",
            color=self.bot.color,
            timestamp=event.timestamp,  # type: ignore
        )
        embed.set_footer("As of")

        chan_id, msg_id = event.live_online_channel.split("|")

        fake_msg = ipy.Message(client=self.bot, id=int(msg_id), channel_id=int(chan_id))  # type: ignore

        try:
            await fake_msg.edit(embed=embed)
        except ipy.errors.HTTPException:
            await pl_utils.eventually_invalidate_live_online(self.bot, event.config)

    @ipy.listen("realm_down", is_default_listener=True)
    async def realm_down(self, event: pl_events.RealmDown) -> None:
        # live playerlists are time sensitive, get them out first
        if self.bot.live_playerlist_store[event.realm_id]:
            self.bot.dispatch(
                pl_events.LivePlayerlistSend(
                    event.realm_id, set(), event.disconnected, event.timestamp
                )
            )

        # these, meanwhile, aren't
        async for config in event.configs:
            if not config.playerlist_chan or not config.realm_offline_role:
                continue

            guild = self.bot.get_guild(config.guild_id)
            if not guild:
                continue

            role_mention = f"<@&{config.realm_offline_role}>"

            embed = ipy.Embed(
                title="Realm Offline",
                description=(
                    "The bot has detected that the Realm is offline (or possibly that"
                    " it has no users)."
                ),
                timestamp=ipy.Timestamp.fromdatetime(event.timestamp),
                color=ipy.RoleColors.YELLOW,
            )

            try:
                chan = await pl_utils.fetch_playerlist_channel(self.bot, guild, config)
                await chan.send(
                    role_mention,
                    embeds=embed,
                    allowed_mentions=ipy.AllowedMentions.all(),
                )
            except ValueError:
                continue
            except ipy.errors.HTTPException:
                await pl_utils.eventually_invalidate(self.bot, config)
                continue

    @ipy.listen("warn_missing_playerlist", is_default_listener=True)
    async def warning_missing_playerlist(
        self, event: pl_events.WarnMissingPlayerlist
    ) -> None:
        no_playerlist_chan: list[bool] = []

        async for config in event.configs:
            if not config.playerlist_chan:
                if config.realm_id and config.live_playerlist:
                    self.bot.live_playerlist_store[config.realm_id].discard(
                        config.guild_id
                    )

                config.realm_id = None
                config.club_id = None
                config.live_playerlist = False
                config.fetch_devices = False

                await config.save()

                no_playerlist_chan.append(True)
                continue

            no_playerlist_chan.append(False)

            if not config.warning_notifications:
                continue

            guild = self.bot.get_guild(config.guild_id)
            if not guild:
                # could just be it's offline or something
                continue

            await pl_utils.eventually_invalidate(self.bot, config, limit=7)

            try:
                chan = await pl_utils.fetch_playerlist_channel(self.bot, guild, config)
            except ValueError:
                continue

            with contextlib.suppress(ipy.errors.HTTPException):
                embed = ipy.Embed(
                    title="Warning",
                    description=(
                        "I have been unable to get any information about your Realm"
                        " for the last 24 hours. This could be because the Realm has"
                        " been turned off or because it's inactive, but if it hasn't,"
                        " make sure you haven't banned or kick"
                        f" `{self.bot.own_gamertag}`. If you have, please unban the"
                        " account if needed and run"
                        f" {self.bot.mention_cmd('config link-realm')} again to"
                        " fix it.\n\nAlternatively, if you want to disable the"
                        " autorunner entirely, you can use"
                        f" {self.bot.mention_cmd('config playerlist-channel')} to"
                        " do so."
                    ),
                    color=ipy.RoleColors.YELLOW,
                )
                await chan.send(embeds=embed)

        if all(no_playerlist_chan) or not no_playerlist_chan:
            self.bot.fetch_devices_for.discard(event.realm_id)

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
                else:
                    raise


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(pl_events)
    importlib.reload(pl_utils)
    PlayerlistEventHandling(bot)
