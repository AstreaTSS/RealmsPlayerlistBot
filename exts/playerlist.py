"""
Copyright 2020-2024 AstreaTSS.
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

import asyncio
import datetime
import importlib
import math
import time
import typing
from collections import defaultdict

import elytra
import interactions as ipy
import tansy

import common.classes as cclasses
import common.models as models
import common.playerlist_events as pl_events
import common.playerlist_utils as pl_utils
import common.utils as utils


class PlayerlistKwargs(typing.TypedDict, total=False):
    autorunner: bool
    upsell: str | None
    gamertag_map: defaultdict[str, str]


class Playerlist(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.name = "Playerlist Related"

        self.previous_now = datetime.datetime.now(tz=datetime.UTC)
        self.forbidden_count: int = 0

        if utils.FEATURE("PROCESS_REALMS"):
            self.get_people_task = self.bot.create_task(self.get_people_runner())

    def drop(self) -> None:
        if utils.FEATURE("PROCESS_REALMS"):
            self.get_people_task.cancel()
        super().drop()

    def next_time(self) -> ipy.Timestamp:
        now = ipy.Timestamp.utcnow()
        # margin of error
        multiplicity = math.ceil((now.timestamp() + 0.1) / 60)
        next_time = multiplicity * 60
        return ipy.Timestamp.utcfromtimestamp(next_time)

    async def get_people_runner(self) -> None:
        await self.bot.fully_ready.wait()
        await utils.sleep_until(self.next_time())

        while True:
            next_time = self.next_time()
            try:
                start = time.perf_counter()
                await self.parse_realms()
                end = time.perf_counter()

                if self.previous_now.minute in {0, 30}:
                    ipy.const.get_logger().info(
                        "Ran parse_realms in %s seconds", round(end - start, 3)
                    )

                if utils.FEATURE("HANDLE_MISSING_REALMS"):
                    self.bot.create_task(self.handle_missing_warning())
            except Exception as e:
                if not isinstance(e, asyncio.CancelledError):
                    await utils.error_handle(e)
                else:
                    break
            await utils.sleep_until(next_time)

    async def parse_realms(self) -> None:
        try:
            realms = await self.bot.realms.fetch_activities()
            self.forbidden_count = 0
        except Exception as e:
            if (
                isinstance(e, elytra.MicrosoftAPIException)
                and e.resp.status_code == 502
            ):
                # bad gateway, can't do much about it
                return
            if (
                isinstance(e, elytra.MicrosoftAPIException)
                and e.resp.status_code == 403
            ):
                # oh boy, this one's painful
                self.forbidden_count += 1
                if self.forbidden_count > 3:
                    await utils.msg_to_owner(
                        self.bot,
                        "Got forbidden 3+ times in a row. High chance account is"
                        " banned - please manually check to verify this.",
                    )
            raise

        player_objs: list[models.PlayerSession] = []
        joined_player_objs: list[models.PlayerSession] = []
        gotten_realm_ids: set[int] = set()
        now = datetime.datetime.now(tz=datetime.UTC)

        for realm in realms.servers:
            gotten_realm_ids.add(realm.id)
            player_set: set[str] = set()
            joined: set[str] = set()

            for player in realm.players:
                player_set.add(player.uuid)

                kwargs = {
                    "custom_id": self.bot.uuid_cache[f"{realm.id}-{player.uuid}"],
                    "realm_id": str(realm.id),
                    "xuid": str(player.uuid),
                    "online": True,
                    "last_seen": now,
                }

                if player.uuid not in self.bot.online_cache[realm.id]:
                    joined.add(player.uuid)
                    kwargs["joined_at"] = now
                    joined_player_objs.append(models.PlayerSession(**kwargs))

                    if guild_ids := self.bot.player_watchlist_store[
                        f"{realm.id}-{player.uuid}"
                    ]:
                        self.bot.dispatch(
                            pl_events.PlayerWatchlistMatch(
                                str(realm.id),
                                player.uuid,
                                guild_ids,
                            )
                        )
                else:
                    player_objs.append(models.PlayerSession(**kwargs))

            left = self.bot.online_cache[realm.id].difference(player_set)

            # if all of the players left, there MAY be a crash, but it's hard
            # to tell since they could have all just left during that minute
            # 4 seems like a reasonable threshold to guess for this
            already_sent_realm_down = False
            if not player_set and len(left) > 4:
                self.bot.dispatch(
                    pl_events.RealmDown(
                        str(realm.id),
                        left,
                        now,
                    )
                )
                already_sent_realm_down = True

            self.bot.online_cache[realm.id] = player_set

            if realm.id in self.bot.offline_realms:
                self.bot.offline_realms.discard(realm.id)
                self.bot.dropped_offline_realms.add(realm.id)

            player_objs.extend(
                models.PlayerSession(
                    custom_id=self.bot.uuid_cache.pop(f"{realm.id}-{player}"),
                    realm_id=str(realm.id),
                    xuid=player,
                    online=False,
                    last_seen=self.previous_now,
                )
                for player in left
            )
            if (
                not already_sent_realm_down
                and self.bot.live_playerlist_store[str(realm.id)]
                and (joined or left)
            ):
                self.bot.dispatch(
                    pl_events.LivePlayerlistSend(
                        str(realm.id),
                        joined,
                        left,
                        now,
                    )
                )

        online_cache_ids = set(self.bot.online_cache.keys())
        for missed_realm_id in online_cache_ids.difference(gotten_realm_ids):
            # adds the missing realm id to the countdown timer dict

            self.bot.offline_realms.add(missed_realm_id)

            now_invalid = self.bot.online_cache.pop(missed_realm_id, None)
            if not now_invalid:
                continue

            player_objs.extend(
                models.PlayerSession(
                    custom_id=self.bot.uuid_cache.pop(f"{missed_realm_id}-{player}"),
                    realm_id=str(missed_realm_id),
                    xuid=player,
                    online=False,
                    last_seen=self.previous_now,
                )
                for player in now_invalid
            )
            self.bot.dispatch(
                pl_events.RealmDown(
                    str(missed_realm_id),
                    now_invalid,
                    now,
                )
            )

        self.previous_now = now

        self.bot.dispatch(
            pl_events.PlayerlistParseFinish(
                (
                    pl_utils.RealmPlayersContainer(player_sessions=player_objs),
                    pl_utils.RealmPlayersContainer(
                        player_sessions=joined_player_objs, fields=("joined_at",)
                    ),
                )
            )
        )

    async def handle_missing_warning(self) -> None:
        # basically, for every realm that has been determined to be offline/missing -
        # increase its value by one. if it increases more than a set value,
        # try to warn the user about the realm not being there
        # ideally, this should run every minute

        offline_realms = self.bot.offline_realms.copy()

        async with self.bot.redis.pipeline() as pipe:
            for realm_id in offline_realms:
                pipe.incr(f"missing-realm-{realm_id}", 1)

            results: list[int] = await pipe.execute()

        for realm_id, value in zip(offline_realms, results, strict=True):
            if value >= 1440:
                self.bot.dispatch(pl_events.WarnMissingPlayerlist(str(realm_id)))
                self.bot.dropped_offline_realms.add(realm_id)

        if self.bot.dropped_offline_realms:
            await self.bot.redis.delete(
                *(f"missing-realm-{rid}" for rid in self.bot.dropped_offline_realms)
            )
            self.bot.dropped_offline_realms = set()

    @tansy.slash_command(
        name="playerlist",
        description="Sends a playerlist, a log of players who have joined and left.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )
    @ipy.check(pl_utils.has_linked_realm)
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 60)
    async def playerlist(
        self,
        ctx: utils.RealmContext | utils.RealmPrefixedContext,
        hours_ago: int = tansy.Option(
            "How far back the playerlist should go (in hours). Defaults to 12"
            " hours. Max of 24 hours.",
            min_value=1,
            max_value=24,
            default=12,
        ),
        **kwargs: typing.Unpack[PlayerlistKwargs],
    ) -> None:
        """
        Checks and makes a playerlist, a log of players who have joined and left.
        The autorunning version only goes back an hour.

        Has a cooldown of 60 seconds due to how intensive this command can be.
        May take a while to run at first.
        """

        autorunner = kwargs.get("autorunner", False)
        upsell = kwargs.get("upsell")
        gamertag_map: defaultdict[str, str] | None = kwargs.get("gamertag_map")

        config = await ctx.fetch_config()

        if gamertag_map:
            gamertag_map |= config.nicknames

        # this may seem a bit weird to you... but let's say it's 8:00:03, and we want to
        # go one hour back
        # a naive implementation would just subtract one hour from the time, getting 7:00:03,
        # but there may be entries that were stored from 7:00:01 because of how the data collector
        # runs
        # instead, we set the seconds to 30 (8:00:30), then subtract the hours and one minute,
        # which results in 6:59:30 - effectively, we're getting times from 7:00:00 onwards,
        # as the data collector thing will not take a whole 30 seconds to process things
        # this is very useful for the autorunners, which always have a chance of taking a bit
        # long due to random chance
        now = ipy.Timestamp.utcnow().replace(second=30)
        time_delta = datetime.timedelta(hours=hours_ago, minutes=1)
        time_ago = now - time_delta

        hour_text = "hour" if hours_ago == 1 else "hours"

        player_sessions = await models.PlayerSession.prisma().find_many(
            distinct=["xuid"],
            order=[{"xuid": "asc"}, {"last_seen": "desc"}],
            where={
                "realm_id": str(config.realm_id),
                "OR": [{"online": True}, {"last_seen": {"gte": time_ago}}],
            },
        )

        if not player_sessions:
            if autorunner:
                return

            raise utils.CustomCheckFailure(
                "No one seems to have been on the Realm for the last"
                f" {hours_ago} {hour_text}."
            )

        bypass_cache_for: typing.Optional[set[str]] = None
        if config.fetch_devices:
            if not config.valid_premium:
                if isinstance(config, models.AutorunGuildConfig):
                    config = await models.GuildConfig.prisma().find_unique_or_raise(
                        where={"guild_id": config.guild_id}
                    )
                await pl_utils.invalidate_premium(self.bot, config)
            else:
                bypass_cache_for = {p.xuid for p in player_sessions if p.online}

        player_list = await pl_utils.fill_in_gamertags_for_sessions(
            self.bot,
            player_sessions,
            bypass_cache_for=bypass_cache_for,
            gamertag_map=gamertag_map,
        )

        online_list = sorted(
            (p.display for p in player_list if p.online), key=lambda g: g.lower()
        )
        offline_list = [
            p.display
            for p in sorted(
                (p for p in player_list if not p.online),
                key=lambda p: p.last_seen.timestamp(),
                reverse=True,
            )
        ]

        embeds: list[ipy.Embed] = []
        timestamp = ipy.Timestamp.fromdatetime(self.previous_now)

        if online_list:
            embeds.append(
                ipy.Embed(
                    color=ipy.Color.from_hex("7abd59"),
                    title="People online right now",
                    description="\n".join(online_list),
                    footer=ipy.EmbedFooter(text="As of"),
                    timestamp=timestamp,
                )
            )

        if offline_list:
            offline_embeds: list[ipy.Embed] = []

            current_entries: list[str] = []
            current_length: int = 0

            for entry in offline_list:
                current_length += len(entry)
                if current_length > 3900:
                    offline_embeds.append(
                        ipy.Embed(
                            color=ipy.Color.from_hex("95a5a6"),
                            description="\n".join(current_entries),
                            footer=ipy.EmbedFooter(text="As of"),
                            timestamp=timestamp,
                        )
                    )
                    current_entries = []
                    current_length = 0

                current_entries.append(entry)

            if current_entries:
                offline_embeds.append(
                    ipy.Embed(
                        color=ipy.Color.from_hex("95a5a6"),
                        description="\n".join(current_entries),
                        footer=ipy.EmbedFooter(text="As of"),
                        timestamp=timestamp,
                    )
                )

            offline_embeds[0].title = f"People on in the last {hours_ago} {hour_text}"
            embeds.extend(offline_embeds)

        if upsell and not config.valid_premium:
            # add upsell message to last embed
            embeds[-1].set_footer(upsell)

        first_embed = True

        for embed in embeds:
            # each embed can border very close to the max character in a message limit,
            # so we have to send each one individually

            if autorunner and first_embed:
                # if we're using the autorunner, add a little message to note that
                # this is a log
                await ctx.send(
                    content=f"Autorunner log for {timestamp.format('f')}:",
                    embed=embed,
                )
                first_embed = False
            else:
                await ctx.send(embeds=embed)

    @tansy.slash_command(
        "online",
        description="Allows you to see if anyone is online on the Realm right now.",
        dm_permission=False,
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 10)
    @ipy.check(pl_utils.has_linked_realm)
    async def online(
        self,
        ctx: utils.RealmContext,
        device_information: bool = tansy.Option(
            "Should the bot fetch and display device information? Requires voting or"
            " Premium.",
            default=False,
        ),
    ) -> None:
        """
        Allows you to see if anyone is online on the Realm right now.
        Has a cooldown of 10 seconds.
        """
        config = await ctx.fetch_config()

        player_sessions = await models.PlayerSession.prisma().find_many(
            where={"realm_id": str(config.realm_id), "online": True}
        )

        # okay, this is going to get complicated
        bypass_cache = False

        if device_information:
            if (
                not config.valid_premium
                and utils.SHOULD_VOTEGATE
                and await self.bot.redis.get(f"rpl-voted-{ctx.author_id}") != "1"
            ):
                raise utils.CustomCheckFailure(
                    "To get device information, you must vote for the bot through one"
                    f" of the links listed in {self.bot.mention_command('vote')} or"
                    " [purchase Playerlist"
                    " Premium](https://rpl.astrea.cc/wiki/premium.html). Voting lasts"
                    " for 12 hours."
                )
            else:
                bypass_cache = True
        elif config.fetch_devices:
            if config.valid_premium:
                bypass_cache = True
            else:
                await pl_utils.invalidate_premium(self.bot, config)

        playerlist = await pl_utils.fill_in_gamertags_for_sessions(
            self.bot,
            player_sessions,
            bypass_cache=bypass_cache,
            gamertag_map=config.nicknames,
        )

        if not (
            online_list := sorted(
                (p.display for p in playerlist if p.online),
                key=lambda g: g.lower(),
            )
        ):
            raise utils.CustomCheckFailure("No one is on the Realm right now.")

        embed = ipy.Embed(
            color=self.bot.color,
            title=f"{len(online_list)}/10 people online",
            description="\n".join(online_list),
            footer=ipy.EmbedFooter(text="As of"),
            timestamp=ipy.Timestamp.fromdatetime(self.previous_now),
        )
        await ctx.send(embed=embed)


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(cclasses)
    importlib.reload(pl_events)
    importlib.reload(pl_utils)
    Playerlist(bot)
