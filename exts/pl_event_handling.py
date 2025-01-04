"""
Copyright 2020-2025 AstreaTSS.
This file is part of the Realms Playerlist Bot.

The Realms Playerlist Bot is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

The Realms Playerlist Bot is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with the Realms
Playerlist Bot. If not, see <https://www.gnu.org/licenses/>.
"""

import contextlib
import importlib
import logging
import os
import typing

import elytra
import interactions as ipy

import common.models as models
import common.playerlist_events as pl_events
import common.playerlist_utils as pl_utils
import common.utils as utils

logger = logging.getLogger("realms_bot")


class PlayerlistEventHandling(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.name = "Playerlist Event Handling"

    @ipy.listen("playerlist_parse_finish", is_default_listener=True)
    async def on_playerlist_finish(
        self, event: pl_events.PlayerlistParseFinish
    ) -> None:
        async with self.bot.db.batch_() as batch:
            for container in event.containers:
                for session in container.player_sessions:
                    batch.playersession.upsert(
                        where={"custom_id": session.custom_id},
                        data={
                            "create": session.model_dump(exclude_defaults=True),
                            "update": session.model_dump(include=set(container.fields)),
                        },  # type: ignore
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
                last_seen=event.timestamp,
                show_left=False,
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

        base_embed = ipy.Embed(
            color=ipy.RoleColors.DARK_GREY,
            timestamp=ipy.Timestamp.fromdatetime(event.timestamp),
        )
        base_embed.set_footer(
            f"{len(self.bot.online_cache[int(event.realm_id)])} players online as of"
        )

        for guild_id in self.bot.live_playerlist_store[event.realm_id].copy():
            config = await models.GuildConfig.get_or_none(guild_id)

            if not config:
                self.bot.live_playerlist_store[event.realm_id].discard(guild_id)
                continue

            if not config.valid_premium:
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

            if guild_id in self.bot.unavailable_guilds:
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
                        realm_down_event=event.realm_down_event,
                    )
                )

            embed = ipy.Embed.from_dict(base_embed.to_dict())

            if event.joined:
                embed.add_field(
                    name=f"{os.environ['GREEN_CIRCLE_EMOJI']} Joined",
                    value="\n".join(
                        sorted(
                            (
                                config.nicknames.get(p) or gamertag_mapping[p]
                                for p in event.joined
                            ),
                            key=lambda x: x.lower(),
                        )
                    ),
                )
            if event.left:
                embed.add_field(
                    name=f"{os.environ['GRAY_CIRCLE_EMOJI']} Left",
                    value="\n".join(
                        sorted(
                            (
                                config.nicknames.get(p) or gamertag_mapping[p]
                                for p in event.left
                            ),
                            key=lambda x: x.lower(),
                        )
                    ),
                )

            try:
                chan = utils.partial_channel(self.bot, config.playerlist_chan)
                await chan.send(embeds=embed)
            except ValueError:
                continue
            except ipy.errors.HTTPException as e:
                if e.status < 500:
                    await pl_utils.eventually_invalidate(self.bot, config)
                    continue

    @ipy.listen("live_online_update", is_default_listener=True)
    async def on_live_online_update(self, event: pl_events.LiveOnlineUpdate) -> None:
        xuid_str: str | None = await self.bot.valkey.hget(
            event.live_online_channel, "xuids"
        )
        gamertag_str: str | None = await self.bot.valkey.hget(
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

        await self.bot.valkey.hset(
            event.live_online_channel, "xuids", ",".join(xuid_list)
        )
        await self.bot.valkey.hset(
            event.live_online_channel, "gamertags", new_gamertag_str
        )

        if event.realm_down_event:
            new_gamertag_str = f"{os.environ['GRAY_CIRCLE_EMOJI']} *Realm is offline.*"
        else:
            actual_gamertag_list = sorted(
                (
                    event.config.nicknames.get(xuid) or event.gamertag_mapping[xuid]
                    for xuid in xuids
                ),
                key=lambda g: g.lower(),
            )
            new_gamertag_str = "\n".join(actual_gamertag_list)

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
        except ipy.errors.HTTPException as e:
            if e.status < 500:
                await pl_utils.eventually_invalidate_live_online(self.bot, event.config)

    @ipy.listen("realm_down", is_default_listener=True)
    async def realm_down(self, event: pl_events.RealmDown) -> None:
        # live playerlists are time sensitive, get them out first
        if self.bot.live_playerlist_store[event.realm_id]:
            self.bot.dispatch(
                pl_events.LivePlayerlistSend(
                    event.realm_id,
                    set(),
                    event.disconnected,
                    event.timestamp,
                    realm_down_event=True,
                )
            )

        # these, meanwhile, aren't
        for config in await event.configs():
            if not config.playerlist_chan or not config.realm_offline_role:
                continue

            if config.guild_id in self.bot.unavailable_guilds:
                continue

            role_mention = f"<@&{config.realm_offline_role}>"

            embed = ipy.Embed(
                title="Realm Offline",
                description=(
                    "The bot has detected that the Realm has gone offline (or that all"
                    " users have left it)."
                ),
                timestamp=ipy.Timestamp.fromdatetime(event.timestamp),
                color=ipy.RoleColors.YELLOW,
            )

            try:
                chan = utils.partial_channel(
                    self.bot,
                    config.get_notif_channel("realm_offline"),
                )

                await chan.send(
                    role_mention,
                    embeds=embed,
                    allowed_mentions=ipy.AllowedMentions.all(),
                )
            except (ipy.errors.HTTPException, ValueError):
                if config.notification_channels.get("realm_offline"):
                    await pl_utils.eventually_invalidate_realm_offline(self.bot, config)
                else:
                    await pl_utils.eventually_invalidate(self.bot, config)
                continue

    @ipy.listen("warn_missing_playerlist", is_default_listener=True)
    async def warning_missing_playerlist(
        self, event: pl_events.WarnMissingPlayerlist
    ) -> None:
        no_playerlist_chan: list[bool] = []

        for config in await event.configs():
            if not config.playerlist_chan:
                if config.realm_id and config.live_playerlist:
                    self.bot.live_playerlist_store[config.realm_id].discard(
                        config.guild_id
                    )

                if config.realm_id:
                    self.bot.offline_realms.discard(int(config.realm_id))

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

            if config.guild_id in self.bot.unavailable_guilds:
                continue

            logger.info("Warning %s for missing Realm.", config.guild_id)

            await pl_utils.eventually_invalidate(self.bot, config, limit=7)

            if not config.playerlist_chan:
                continue

            chan = utils.partial_channel(self.bot, config.playerlist_chan)

            with contextlib.suppress(ipy.errors.HTTPException):
                content = (
                    "I have been unable to get any information about your Realm for"
                    " the last 24 hours. This could be because the Realm has been"
                    " turned off or because it's inactive, but if it hasn't, make sure"
                    f" you haven't banned or kick `{self.bot.own_gamertag}`. If you"
                    " have, please unban the account if needed and run"
                    f" {self.bot.mention_command('config link-realm')} again to fix"
                    " it.\n\nAlternatively:\n- If you want to disable the autorunning"
                    " playerlist entirely, you can use"
                    f" {self.bot.mention_command('config autorunning-playerlist-channel')} to"
                    " do so.\n- If you want to disable this warning, you can use"
                    f" {self.bot.mention_command('config realm-warning')} to do so."
                    " *Note that these warnings are often useful, so disabling is not"
                    " recommended unless you expect your Realm to be inactive for days"
                    " on end.*\n\nThe bot will automatically disable the autorunning"
                    " playerlist and related settings after 7 days of not getting"
                    " information from your Realm."
                )
                await chan.send(content=content)

        if all(no_playerlist_chan) or not no_playerlist_chan:
            self.bot.live_playerlist_store.pop(event.realm_id, None)
            self.bot.fetch_devices_for.discard(event.realm_id)
            self.bot.offline_realms.discard(int(event.realm_id))

            # we don't want to stop the whole thing, but as of right now i would
            # like to know what happens with invalid stuff
            try:
                await self.bot.realms.leave_realm(event.realm_id)
            except elytra.MicrosoftAPIException as e:
                # might be an invalid id somehow? who knows
                if e.resp.status_code == 404:
                    logger.warning("Could not leave Realm with ID %s.", event.realm_id)
                else:
                    raise

    @ipy.listen(pl_events.PlayerWatchlistMatch, is_default_listener=True)
    async def watchlist_notify(self, event: pl_events.PlayerWatchlistMatch) -> None:
        for config in await event.configs():
            if not config.playerlist_chan or not config.player_watchlist:
                self.bot.player_watchlist_store[
                    f"{event.realm_id}-{event.player_xuid}"
                ].discard(config.guild_id)
                config.player_watchlist = []
                await config.save()
                continue

            try:
                chan = utils.partial_channel(
                    self.bot,
                    config.get_notif_channel("player_watchlist"),
                )

                if config.nicknames.get(event.player_xuid):
                    gamertag = config.nicknames[event.player_xuid]
                else:
                    try:
                        gamertag = await pl_utils.gamertag_from_xuid(
                            self.bot, event.player_xuid
                        )
                    except ipy.errors.BadArgument:
                        gamertag = f"Player with XUID {event.player_xuid}"

                content = ""
                if config.player_watchlist_role:
                    content = f"<@&{config.player_watchlist_role}>, "

                content += f"`{gamertag}` joined the Realm!"

                await chan.send(
                    content,
                    allowed_mentions=ipy.AllowedMentions.all(),
                )
            except (ipy.errors.HTTPException, ValueError):
                if config.notification_channels.get("player_watchlist"):
                    await pl_utils.eventually_invalidate_watchlist(self.bot, config)
                else:
                    await pl_utils.eventually_invalidate(self.bot, config)
                continue


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(pl_events)
    importlib.reload(pl_utils)
    PlayerlistEventHandling(bot)
