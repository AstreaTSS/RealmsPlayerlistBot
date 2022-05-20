import asyncio
import contextlib
import datetime
import importlib
import os
import typing
from enum import IntEnum

import aiohttp
import attr
import nextcord
import orjson
from nextcord.ext import commands
from pydantic import ValidationError
from tortoise.exceptions import DoesNotExist
from xbox.webapi.api.provider.profile.models import ProfileResponse

import common.custom_providers as providers
import common.utils as utils

"""
Hey, potential code viewer!
If you're looking at this, chances are you're interested in how this works.
First thing: it's December 12st 2021 right now, and I made large chunks of this a year or more back.
Even I don't quite know every part of it - it's been lost to time and bad programming practices.

Most of this code is not pretty and probably could be made better.
But at the same time, this code works, and poking around is not fun.
Also, this isn't exactly my favorite bot. It's a huge pain to maintain.
Oh well. Honestly, it could be a lot worse.

Also also (yeah), this approach is a somewhat hacky exploit of how Realms work.
Every Realm creates a club for it to use - in Minecraft itself, you can view this by clicking
the whole photo view thing while in a Realm.
This is largely used just to share photos and info, but I did a deep dive on this and found out
it can also be used to see who was online and who was offline.
You can do this via the Xbox app, actually - I believe if you're in a Realm, you should automatically
join the Relam club, so just check that and search for the section that has all of the players in it.
The problem is that that section doesn't tell you enough - it doesn't tell you when they were last on, for example.
This bot basically combines all of that knowledge together, gets the club of the Realm via the Xbox Live API since it is
an Xbox Live thing, gets the people who were on, and puts out one easy to use playerlist to be used for
moderation (or really, whatever you would like).

Sadly, commenting on what everything does in-depth is a waste of time, since I tend to make most of my code
self-documenting. I don't find use in commenting what can be seen directly from the code.
Admittedly, some parts of this are both hard to understand AND uncommented. Sorry! It's just really hard
to comment on those things.

Regardless, good luck on your bot coding journey!
- Astrea
"""


def _camel_to_const_snake(s):
    return "".join([f"_{c}" if c.isupper() else c.upper() for c in s]).lstrip("_")


class ClubUserPresence(IntEnum):
    UNKNOWN = -1
    NOT_IN_CLUB = 0
    IN_CLUB = 1
    CHAT = 2
    FEED = 3
    ROSTER = 4
    PLAY = 5
    IN_GAME = 6

    @classmethod
    def from_xbox_api(cls, value: str):
        try:
            return cls[_camel_to_const_snake(value)]
        except KeyError:
            # it's not like i forgot a value, it's just that some are
            # literally not documented
            return cls.UNKNOWN


@attr.s(slots=True, eq=False)
class Player:
    """A simple class to represent a player on a Realm."""

    xuid: str = attr.ib()
    last_seen: datetime.datetime = attr.ib()
    last_seen_state: ClubUserPresence = attr.ib()
    gamertag: typing.Optional[str] = attr.ib(default=None)

    def __eq__(self, o: object) -> bool:
        return o.xuid == self.xuid if isinstance(o, self.__class__) else False

    @property
    def resolved(self):
        return bool(self.gamertag)

    @property
    def in_game(self):
        return self.last_seen_state == ClubUserPresence.IN_GAME

    @property
    def display(self):  # sourcery skip: remove-unnecessary-else
        base = f"`{self.gamertag}`" if self.gamertag else f"User with XUID {self.xuid}"

        if self.in_game:
            return base
        else:
            time_format = nextcord.utils.format_dt(self.last_seen)
            return f"{base}: last seen {time_format}"


class GamertagOnCooldown(Exception):
    # used by GamertagHandler to know when to switch to the backup
    def __init__(self) -> None:
        # i could make this anything since this should never be exposed
        # to the user, but who knows
        super().__init__("The gamertag handler is on cooldown!")


class GamertagServiceDown(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The gamertag service is down! The bot is unavailable at this time."
        )


class ClubOnCooldown(Exception):
    def __init__(self) -> None:
        super().__init__("The club handler is on cooldown!")


@attr.s(slots=True)
class GamertagHandler:
    """A special class made to handle the complexities of getting gamertags
    from XUIDs."""

    bot: utils.RealmBotBase = attr.ib()
    sem: asyncio.Semaphore = attr.ib()
    xuids_to_get: typing.Tuple[str, ...] = attr.ib()
    profile: "providers.ProfileProvider" = attr.ib()
    openxbl_session: aiohttp.ClientSession = attr.ib()

    index: int = attr.ib(init=False, default=0)
    responses: typing.List["ProfileResponse"] = attr.ib(init=False, factory=list)
    AMOUNT_TO_GET: int = attr.ib(init=False, default=30)

    async def get_gamertags(self, xuid_list: typing.List[str]) -> None:
        # honestly, i forget what this output can look like by now -
        # but if i remember, it's kinda weird
        profile_resp = await self.profile.get_profiles(xuid_list)
        profile_json = await profile_resp.json(loads=orjson.loads)

        if profile_json.get("code"):  # usually means ratelimited or invalid xuid
            description: str = profile_json["description"]

            if description.startswith("Throttled"):  # ratelimited
                raise GamertagOnCooldown()

            # otherwise, invalid xuid
            desc_split = description.split(" ")
            xuid_list.remove(desc_split[1])

            await self.get_gamertags(
                xuid_list
            )  # after removing, try getting data again

        elif profile_json.get("limitType"):  # ratelimit
            raise GamertagOnCooldown()

        self.responses.append(ProfileResponse.parse_obj(profile_json))
        self.index += self.AMOUNT_TO_GET

    async def backup_get_gamertags(self):
        # openxbl is used throughout this, and its basically a way of navigating
        # the xbox live api in a more sane way than its actually laid out
        # while xbox-webapi-python can also do this without using a 3rd party service,
        # using openxbl can be more reliable at times as it has a generous 500 requests
        # per hour limit on the free tier and is not subject to ratelimits
        # however, there's no bulk xuid > gamertag option, and is a bit slow in general

        for xuid in self.xuids_to_get[self.index :]:
            async with self.openxbl_session.get(
                f"https://xbl.io/api/v2/account/{xuid}"
            ) as r:
                try:
                    resp_json = await r.json(loads=orjson.loads)
                    if "code" in resp_json.keys():  # service is down
                        await utils.msg_to_owner(self.bot, resp_json)
                        raise GamertagServiceDown()
                    else:
                        with contextlib.suppress(ValidationError):
                            self.responses.append(ProfileResponse.parse_obj(resp_json))
                except aiohttp.ContentTypeError:
                    # can happen, if not rare
                    text = await r.text()
                    await utils.msg_to_owner(
                        self.bot,
                        f"Failed to get gamertag of user `{xuid}`.\nResponse code:"
                        f" {r.status}\nText: {text}",
                    )

            self.index += 1

    async def run(self):
        while self.index < len(self.xuids_to_get):
            current_xuid_list = list(self.xuids_to_get[self.index : self.index + 30])

            async with self.sem:
                with contextlib.suppress(GamertagOnCooldown):
                    await self.get_gamertags(current_xuid_list)
                # alright, so we either got 30 gamertags or are ratelimited
                # so now we switch to the backup getter so that we don't have
                # to wait on the ratelimit to request for more gamertags
                # this wait_for basically a little 'exploit` to only make the backup
                # run for 15 seconds or until completetion, whatever comes first
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self.backup_get_gamertags(), timeout=15)
        dict_gamertags: typing.Dict[str, str] = {}

        for profiles in self.responses:
            for user in profiles.profile_users:
                try:
                    # really funny but efficient way of getting gamertag
                    # from this data
                    gamertag = next(
                        s.value for s in user.settings if s.id == "Gamertag"
                    )
                    await self.bot.redis.setex(
                        name=str(user.id),
                        time=datetime.timedelta(days=14),
                        value=gamertag,
                    )
                    dict_gamertags[user.id] = gamertag
                except (KeyError, StopIteration):
                    continue

        return dict_gamertags


class HourConverter(commands.Converter[int], int):
    async def convert(self, ctx: commands.Context, argument: str):
        argument = argument.lower().replace("h", "", 1)

        if not argument.isdigit():
            raise commands.BadArgument("This argument is not a valid number!")

        int_argument = int(argument)
        if not 1 <= int_argument <= 24:
            raise commands.BadArgument("The duration is not in between 1-24 hours!")

        return int_argument


async def can_run_playerlist(ctx: utils.RealmContext):
    # simple check to see if a person can run the playerlist command
    try:
        guild_config = await ctx.fetch_config()
    except DoesNotExist:
        return False
    return bool(guild_config.club_id)


async def can_run_online(ctx: utils.RealmContext):
    # same, but for the online command
    try:
        guild_config = await ctx.fetch_config()
    except DoesNotExist:
        return False
    return bool(guild_config.club_id) and guild_config.online_cmd


class Playerlist(commands.Cog):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.sem = asyncio.Semaphore(
            3
        )  # prevents bot from overloading xbox api, hopefully

        headers = {
            "X-Authorization": os.environ["OPENXBL_KEY"],
            "Accept": "application/json",
            "Accept-Language": "en-US",
        }
        self.openxbl_session = aiohttp.ClientSession(headers=headers)

    def cog_unload(self):
        self.bot.loop.create_task(self.openxbl_session.close())

    async def _realm_club_json(
        self, club_id
    ) -> typing.Tuple[typing.Optional[dict], aiohttp.ClientResponse]:
        try:
            r = await self.bot.club.get_club_user_presences(club_id)
            if r.status == 429:
                # ratelimit, use openxbl instead
                raise ClubOnCooldown()

            resp_json = await r.json(loads=orjson.loads)
            return resp_json, r
        except (aiohttp.ContentTypeError, ClubOnCooldown):
            async with self.openxbl_session.get(
                f"https://xbl.io/api/v2/clubs/{club_id}"
            ) as r:
                try:
                    resp_json = await r.json(loads=orjson.loads)
                    return resp_json, r
                except aiohttp.ContentTypeError:
                    return None, r

    async def realm_club_get(self, club_id):
        resp_json, resp = await self._realm_club_json(club_id)

        if not resp_json:
            resp_text = await resp.text()
            await utils.msg_to_owner(self.bot, resp_text)
            await utils.msg_to_owner(self.bot, resp.headers)
            await utils.msg_to_owner(self.bot, resp.status)
            return None

        try:
            # again, the xbox live api gives every response as a list
            # even when requesting for one thing
            # and we only need the presences of the users
            # not the other stuff
            return resp_json["clubs"][0]["clubPresence"]
        except (KeyError, TypeError):
            # who knows x2

            if resp_json.get("code") and resp_json["code"] == 1018:
                return "Unauthorized"

            await utils.msg_to_owner(self.bot, resp_json)
            await utils.msg_to_owner(self.bot, resp.headers)
            await utils.msg_to_owner(self.bot, resp.status)
            return None

    async def get_players_from_club_data(
        self,
        club_presence: typing.List[typing.Dict],
        time_ago: typing.Optional[datetime.datetime] = None,
        online_only: bool = False,
    ):
        player_list: typing.List[Player] = []
        unresolved_dict: typing.Dict[str, Player] = {}

        for member in club_presence:
            last_seen_state = ClubUserPresence.from_xbox_api(member["lastSeenState"])

            if last_seen_state not in {
                ClubUserPresence.IN_GAME,
                ClubUserPresence.NOT_IN_CLUB,
            }:
                # we want to ignore people causally browsing the club itself
                # this isn't perfect, as if they stop viewing the club, they'll be put in
                # the "NotInClub" list, but that's fine
                continue

            # if we're online only, breaking out when we stop getting online
            # people is a good idea
            if online_only and last_seen_state == ClubUserPresence.NOT_IN_CLUB:
                break

            # xbox live uses a bit more precision than python can understand
            # so we cut out that precision
            last_seen = datetime.datetime.strptime(
                member["lastSeenTimestamp"][:-2], "%Y-%m-%dT%H:%M:%S.%f"
            ).replace(tzinfo=datetime.timezone.utc)

            # if this person was on the realm longer than the time period specified
            # we can stop this for loop
            # useful as otherwise we would do an absurd number of requests getting every
            # single gamertag
            if time_ago and last_seen <= time_ago:
                break

            player = Player(
                member["xuid"],
                last_seen,
                last_seen_state,
                await self.bot.redis.get(member["xuid"]),
            )
            if player.resolved:
                player_list.append(player)
            else:
                unresolved_dict[member["xuid"]] = player

        if unresolved_dict:
            gamertag_handler = GamertagHandler(
                self.bot,
                self.sem,
                tuple(unresolved_dict.keys()),
                self.bot.profile,
                self.openxbl_session,
            )
            gamertag_dict = await gamertag_handler.run()

            for xuid, gamertag in gamertag_dict.items():
                unresolved_dict[xuid].gamertag = gamertag

            player_list.extend(unresolved_dict.values())

        return player_list

    @commands.command(aliases=["player_list", "get_playerlist", "get_player_list"])
    @utils.proper_permissions()
    @commands.check(can_run_playerlist)
    @commands.cooldown(1, 240, commands.BucketType.guild)
    async def playerlist(
        self,
        ctx: utils.RealmContext,
        hours_ago: typing.Optional[str] = None,
        **kwargs,
    ):
        """Checks and makes a playerlist, a log of players who have joined and left.
        By default, the command version goes back 12 hours.
        If you wish for it to go back more, simply do `!?playerlist <# hours ago>`.
        The number provided should be in between 1-24 hours.
        The autorun version only goes back 2 hours.

        Has a cooldown of 4 minutes due to how intensive this command can be.
        May take a while to run at first.
        Requires Manage Server permissions."""

        # i hate doing this but otherwise no clear error code is shown
        actual_hours_ago: int = 12
        if hours_ago:
            try:
                actual_hours_ago = await HourConverter().convert(ctx, hours_ago)
            except commands.BadArgument as e:
                ctx.command.reset_cooldown(ctx)  # yes, this is funny
                raise e

        await ctx.trigger_typing()
        guild_config = await ctx.fetch_config()

        if not kwargs.get("no_init_mes"):
            await ctx.reply("This might take quite a bit. Please be patient.")

        async with ctx.channel.typing():
            now = nextcord.utils.utcnow()

            time_delta = datetime.timedelta(hours=actual_hours_ago)
            time_ago = now - time_delta

            club_presence = await self.realm_club_get(guild_config.club_id)
            if club_presence is None:
                # this can happen
                await ctx.reply(
                    "Seems like the playerlist command failed somehow. Astrea should "
                    + "have the info needed to see what's going on."
                )
                return
            elif club_presence == "Unauthorized":
                await utils.msg_to_owner(self.bot, ctx.guild)
                await ctx.reply(
                    "The bot can't seem to read your Realm! If you changed Realms, make"
                    " sure to let Astrea know. Also, make sure you haven't banned the"
                    " bot's Xbox account from the Realm. If you haven't done either,"
                    " this is probably just internal stuff being weird, and it'll fix"
                    " itself in a bit."
                )
                return

            player_list = await self.get_players_from_club_data(
                club_presence, time_ago=time_ago
            )

            online_list = [p.display for p in player_list if p.in_game]
            offline_list = [p.display for p in player_list if not p.in_game]

            if online_list:
                embed = nextcord.Embed(
                    colour=self.bot.color,
                    title="People online right now",
                    description="\n".join(online_list),
                    timestamp=now,
                )
                embed.set_footer(text="As of")
                await ctx.send(embed=embed)

            if offline_list:
                # gets the offline list in lines of 40
                # basically, it's like
                # [ [list of 40 strings] [list of 40 strings] etc.]
                chunks = [
                    offline_list[x : x + 40] for x in range(0, len(offline_list), 40)
                ]

                first_embed = nextcord.Embed(
                    colour=nextcord.Colour.lighter_gray(),
                    description="\n".join(chunks[0]),
                    title=f"People on in the last {actual_hours_ago} hour(s)",
                    timestamp=now,
                )
                first_embed.set_footer(text="As of")
                await ctx.send(embed=first_embed)

                for chunk in chunks[1:]:
                    embed = nextcord.Embed(
                        colour=nextcord.Colour.lighter_gray(),
                        description="\n".join(chunk),
                        timestamp=now,
                    )
                    embed.set_footer(text="As of")
                    await ctx.send(embed=embed)
                    await asyncio.sleep(0.2)

        if not kwargs.get("no_init_mes"):
            if not online_list and not offline_list:
                raise utils.CustomCheckFailure(
                    "No one has been on the Realm for the last "
                    + f"{actual_hours_ago} hour(s)."
                )

            await ctx.reply("Done!")

    @commands.command()
    @commands.cooldown(1, 300, commands.BucketType.guild)
    @commands.check(can_run_online)
    async def online(self, ctx: utils.RealmContext):
        """Allows you to see if anyone is online on the Realm right now.
        The realm must agree to this being enabled for you to use it."""
        # uses much of the same code as playerlist

        await ctx.trigger_typing()
        guild_config = await ctx.fetch_config()

        await ctx.reply("This might take quite a bit. Please be patient.")

        async with ctx.channel.typing():
            now = nextcord.utils.utcnow()
            club_presence = await self.realm_club_get(guild_config.club_id)
            if club_presence is None:
                # this can happen
                await ctx.reply(
                    "Seems like the playerlist command failed somehow. Astrea "
                    + "should have the info needed to see what's going on."
                )
                return
            elif club_presence == "Unauthorized":
                await utils.msg_to_owner(self.bot, ctx.guild)
                await ctx.reply(
                    "The bot can't seem to read your Realm! If you changed Realms, make"
                    " sure to let Astrea know. Also, make sure you haven't banned the"
                    " bot's Xbox account from the Realm. If you haven't done either,"
                    " this is probably just internal stuff being weird, and it'll fix"
                    " itself in a bit."
                )
                return

            player_list = await self.get_players_from_club_data(
                club_presence, online_only=True
            )

        if online_list := [p.display for p in player_list]:
            embed = nextcord.Embed(
                colour=self.bot.color,
                title=f"{len(online_list)}/10 people online",
                description="\n".join(online_list),
                timestamp=now,
            )
            embed.set_footer(text="As of")
            await ctx.reply(embed=embed)
        else:
            raise utils.CustomCheckFailure("No one is on the Realm right now.")


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(Playerlist(bot))
