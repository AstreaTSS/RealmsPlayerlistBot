import asyncio
import datetime
import importlib
import math
import typing

import naff
import tansy

import common.models as models
import common.playerlist_events as pl_events
import common.playerlist_utils as pl_utils
import common.utils as utils
from common.microsoft_core import MicrosoftAPIException

UPSELLS = {
    1: (
        "Want minute-to-minute updates on your Realm? Check out Live Playerlist on"
        " Playerlist Premium: /premium info"
    ),
    2: "If you like the bot, you can vote for it via /vote!",
}


class Playerlist(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.name = "Playerlist Related"

        self.previous_now = datetime.datetime.now(tz=datetime.UTC)

        self.get_people_task = asyncio.create_task(self.get_people_runner())

    def drop(self) -> None:
        self.get_people_task.cancel()
        super().drop()

    def next_time(self) -> naff.Timestamp:
        now = naff.Timestamp.utcnow()
        # margin of error
        multiplicity = math.ceil((now.timestamp() + 0.1) / 60)
        next_time = multiplicity * 60
        return naff.Timestamp.utcfromtimestamp(next_time)

    async def get_people_runner(self) -> None:
        await self.bot.fully_ready.wait()
        await utils.sleep_until(self.next_time())

        while True:
            try:
                next_time = self.next_time()
                await self.parse_realms()
                await self.handle_missing_warning()
                await utils.sleep_until(next_time)
            except Exception as e:
                if not isinstance(e, asyncio.CancelledError):
                    await utils.error_handle(self.bot, e)
                else:
                    break

    async def parse_realms(self) -> None:
        try:
            realms = await self.bot.realms.fetch_activities()
        except Exception as e:
            if isinstance(e, MicrosoftAPIException) and e.resp.status == 502:
                # bad gateway, can't do much about it
                return
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
            self.bot.offline_realm_time.pop(realm.id, None)

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

            self.bot.offline_realm_time.setdefault(missed_realm_id, 0)

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

        for key, value in self.bot.offline_realm_time.copy().items():
            if value < 1439:  # around 24 hours
                self.bot.offline_realm_time[key] += 1
            else:
                self.bot.dispatch(pl_events.WarnMissingPlayerlist(str(key)))

    # can't be a tansy command due to the weird stuff we do with kwargs
    @tansy.slash_command(
        name="playerlist",
        description="Sends a playerlist, a log of players who have joined and left.",
        default_member_permissions=naff.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )  # type: ignore
    @naff.check(pl_utils.can_run_playerlist)  # type: ignore
    @naff.cooldown(naff.Buckets.GUILD, 1, 60)  # type: ignore
    async def playerlist(
        self,
        ctx: utils.RealmContext | utils.RealmPrefixedContext,
        hours_ago: int = tansy.Option(
            (
                "How far back the playerlist should go (in hours). Defaults to 12"
                " hours. Max of 24 hours."
            ),
            min_value=1,
            max_value=24,
            default=12,
        ),
        **kwargs: typing.Any,
    ) -> None:
        """
        Checks and makes a playerlist, a log of players who have joined and left.
        The autorun version only goes back an hour.

        Has a cooldown of 60 seconds due to how intensive this command can be.
        May take a while to run at first.
        """

        autorunner = kwargs.get("autorunner", False)
        upsell = kwargs.get("upsell", False)
        upsell_type: int = kwargs.get("upsell_type", -1)

        guild_config = await ctx.fetch_config()

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
        now = naff.Timestamp.utcnow().replace(second=30)
        time_delta = datetime.timedelta(hours=hours_ago, minutes=1)
        time_ago = now - time_delta

        # select all values from the player session table where realm id is
        # the realm id in the guild config, and (online is true or
        # the last seen date for the entry is greater than or equal to how
        # far back we want to go). order it by the xuid first (we'll
        # get to distinct, but it won't work if it isn't like this), then by the last
        # seen date from newest to older, and finally only return 1 distinct entry
        # (the first entry in the sort, which is the latest last seen date)
        # per xuid value
        # fmt: off
        player_sessions: list[models.PlayerSession] = await models.PlayerSession.raw(
            f"SELECT DISTINCT ON (xuid) * FROM {models.PlayerSession.Meta.table} "
            f"WHERE realm_id='{guild_config.realm_id}' AND (online=true "
            f"OR last_seen>='{time_ago.isoformat()}') ORDER BY xuid, last_seen DESC"
        )  # type: ignore
        # fmt: on

        if not player_sessions:
            if autorunner:
                return

            raise utils.CustomCheckFailure(
                "No one seems to have been on the Realm for the last"
                f" {hours_ago} hour(s). Make sure you haven't changed Realms or kicked"
                f" the bot's account, `{self.bot.own_gamertag}` - try relinking the"
                f" Realm via {self.bot.mention_cmd('config link-realm')} if that"
                " happens."
            )

        player_list = await pl_utils.get_players_from_player_activity(
            self.bot, guild_config.realm_id, player_sessions  # type: ignore
        )

        online_list = sorted(
            (p.display for p in player_list if p.in_game), key=lambda g: g.lower()
        )
        offline_list = [
            p.display
            for p in sorted(
                player_list, key=lambda p: p.last_seen.timestamp(), reverse=True
            )
            if not p.in_game
        ]

        if not online_list and not offline_list:
            if not autorunner:
                raise utils.CustomCheckFailure(
                    f"No one has been on the Realm for the last {hours_ago} hour(s)."
                )
            else:
                return

        embeds: list[naff.Embed] = []
        timestamp = naff.Timestamp.fromdatetime(self.previous_now)

        if online_list:
            embeds.append(
                naff.Embed(
                    color=self.bot.color,
                    title="People online right now",
                    description="\n".join(online_list),
                    footer=naff.EmbedFooter(text="As of"),
                    timestamp=timestamp,
                )
            )

        if offline_list:
            offline_embeds: list[naff.Embed] = []

            current_entries: list[str] = []
            current_length: int = 0

            for entry in offline_list:
                current_length += len(entry)
                if current_length > 4000:
                    offline_embeds.append(
                        naff.Embed(
                            color=naff.Color.from_hex("95a5a6"),
                            description="\n".join(current_entries),
                            footer=naff.EmbedFooter(text="As of"),
                            timestamp=timestamp,
                        )
                    )
                    current_entries = []
                    current_length = 0

                current_entries.append(entry)

            if current_entries:
                offline_embeds.append(
                    naff.Embed(
                        color=naff.Color.from_hex("95a5a6"),
                        description="\n".join(current_entries),
                        footer=naff.EmbedFooter(text="As of"),
                        timestamp=timestamp,
                    )
                )

            offline_embeds[0].title = f"People on in the last {hours_ago} hour(s)"
            embeds.extend(offline_embeds)

        if upsell and not guild_config.premium_code:
            # add upsell message to last embed
            embeds[-1].set_footer(UPSELLS[upsell_type])

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

            # we also make sure we don't get ratelimited hard
            await asyncio.sleep(0.2)

    @naff.slash_command("online", description="Allows you to see if anyone is online on the Realm right now.", dm_permission=False)  # type: ignore
    @naff.cooldown(naff.Buckets.GUILD, 1, 10)
    @naff.check(pl_utils.can_run_playerlist)  # type: ignore
    async def online(self, ctx: utils.RealmContext) -> None:
        """
        Allows you to see if anyone is online on the Realm right now.
        Has a cooldown of 10 seconds.
        """
        guild_config = await ctx.fetch_config()

        player_sessions = await models.PlayerSession.filter(
            realm_id=guild_config.realm_id, online=True
        )
        playerlist = await pl_utils.get_players_from_player_activity(
            self.bot, guild_config.realm_id, player_sessions  # type: ignore
        )

        if online_list := sorted(
            (p.display for p in playerlist if p.in_game), key=lambda g: g.lower()
        ):
            embed = naff.Embed(
                color=self.bot.color,
                title=f"{len(online_list)}/10 people online",
                description="\n".join(online_list),
                footer=naff.EmbedFooter(text="As of"),
                timestamp=naff.Timestamp.fromdatetime(self.previous_now),
            )
            await ctx.send(embed=embed)
        else:
            raise utils.CustomCheckFailure("No one is on the Realm right now.")


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(pl_events)
    importlib.reload(pl_utils)
    Playerlist(bot)
