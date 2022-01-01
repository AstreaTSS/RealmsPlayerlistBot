import asyncio
import datetime
import importlib
import os
import typing

import aiohttp
import attr
import nextcord
from nextcord.ext import commands
from pydantic import ValidationError
from xbox.webapi.api.provider.profile.models import ProfileResponse

import common.profile_custom as profile
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


@attr.s(slots=True, eq=False)
class Player:
    """A simple class to represent a player on a Realm."""

    xuid: str = attr.ib()
    last_seen: datetime.datetime = attr.ib()
    last_seen_state: str = attr.ib()
    gamertag: typing.Optional[str] = attr.ib(default=None)

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            return False

        return o.xuid == self.xuid

    @property
    def resolved(self):
        return bool(self.gamertag)

    @property
    def in_game(self):
        return self.last_seen_state == "InGame"

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


@attr.s(slots=True)
class GamertagHandler:
    """A special class made to handle the complexities of getting gamertags
    from XUIDs."""

    bot: commands.Bot = attr.ib()
    sem: asyncio.Semaphore = attr.ib()
    xuids_to_get: typing.Tuple[str, ...] = attr.ib()
    profile: "profile.ProfileProvider" = attr.ib()
    openxbl_session: aiohttp.ClientSession = attr.ib()

    index: int = attr.ib(init=False, default=0)
    responses: typing.List["ProfileResponse"] = attr.ib(init=False, factory=list)
    AMOUNT_TO_GET: int = attr.ib(init=False, default=30)

    async def get_gamertags(self, xuid_list: typing.List[str]) -> None:
        # honestly, i forget what this output can look like by now -
        # but if i remember, it's kinda weird
        profile_resp = await self.profile.get_profiles(xuid_list)
        profile_json = await profile_resp.json()

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
                    resp_json = await r.json()
                    if "code" in resp_json.keys():  # service is down
                        await utils.msg_to_owner(self.bot, resp_json)
                        raise GamertagServiceDown()
                    else:
                        try:
                            self.responses.append(ProfileResponse.parse_obj(resp_json))
                        except ValidationError:  # invalid xuid, most likely
                            pass
                except aiohttp.ContentTypeError:
                    # can happen, if not rare
                    await utils.msg_to_owner(
                        self.bot, f"Failed to get gamertag of user {xuid}"
                    )

            self.index += 1

    async def run(self):
        while self.index < len(self.xuids_to_get):
            current_xuid_list = list(self.xuids_to_get[self.index : self.index + 30])

            async with self.sem:
                try:
                    await self.get_gamertags(current_xuid_list)
                except GamertagOnCooldown:
                    pass

                # alright, so we either got 30 gamertags or are ratelimited
                # so now we switch to the backup getter so that we don't have
                # to wait on the ratelimit to request for more gamertags
                # this wait_for basically a little 'exploit` to only make the backup
                # run for 15 seconds or until completetion, whatever comes first
                try:
                    await asyncio.wait_for(self.backup_get_gamertags(), timeout=15)
                except asyncio.TimeoutError:
                    pass

        dict_gamertags: typing.Dict[str, str] = {}

        for profiles in self.responses:
            for user in profiles.profile_users:
                try:
                    # really funny but efficient way of getting gamertag
                    # from this data
                    gamertag = next(
                        s.value for s in user.settings if s.id == "Gamertag"
                    )
                    self.bot.gamertags[user.id] = gamertag
                    dict_gamertags[user.id] = gamertag
                except KeyError or StopIteration:
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


async def can_run_playerlist(ctx: commands.Context):
    # simple check to see if a person can run the playerlist command
    try:
        guild_config = ctx.bot.config[str(ctx.guild.id)]
    except KeyError:
        return False
    return guild_config["club_id"] != "None"


async def can_run_online(ctx: commands.Context):
    # same, but for the online command
    try:
        guild_config = ctx.bot.config[str(ctx.guild.id)]
    except KeyError:
        return False
    return bool(guild_config["club_id"] != "None" and guild_config["online_cmd"])


class Playerlist(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.sem = asyncio.Semaphore(
            3
        )  # prevents bot from overloading xbox api, hopefully

        # headers for openxbl, used for gamertag handling
        headers = {
            "X-Authorization": os.environ.get("OPENXBL_KEY"),
            "Accept": "application/json",
            "Accept-Language": "en-US",
        }
        self.openxbl_session = aiohttp.ClientSession(headers=headers)

    def cog_unload(self):
        self.bot.loop.create_task(self.openxbl_session.close())

    async def realm_club_get(self, club_id):
        headers = {  # same api as the gamerag one
            "X-Authorization": os.environ.get("OPENXBL_KEY"),
            "Accept": "application/json",
            "Accept-Language": "en-US",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"https://xbl.io/api/v2/clubs/{club_id}") as r:

                try:
                    resp_json = await r.json()
                except aiohttp.ContentTypeError:
                    # who knows
                    resp = await r.text()
                    await utils.msg_to_owner(self.bot, resp)
                    await utils.msg_to_owner(self.bot, r.headers)
                    await utils.msg_to_owner(self.bot, r.status)
                    return None

                try:
                    # again, the xbox live api gives every response as a list
                    # even when requesting for one thing
                    # and we only need the presences of the users
                    # not the other stuff
                    return resp_json["clubs"][0]["clubPresence"]
                except KeyError or TypeError:
                    # who knows x2
                    await utils.msg_to_owner(self.bot, resp_json)
                    await utils.msg_to_owner(self.bot, r.headers)
                    await utils.msg_to_owner(self.bot, r.status)
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
            # if we're online only, breaking out when we stop getting online
            # people is a good idea
            if online_only and member["lastSeenState"] != "InGame":
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
                member["lastSeenState"],
                self.bot.gamertags.get(member["xuid"]),
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
        self, ctx: commands.Context, hours_ago: typing.Optional[str] = None, **kwargs,
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

        guild_config = self.bot.config[str(ctx.guild.id)]

        if not kwargs.get("no_init_mes"):
            await ctx.reply("This might take quite a bit. Please be patient.")

        async with ctx.channel.typing():
            now = nextcord.utils.utcnow()

            time_delta = datetime.timedelta(hours=actual_hours_ago)
            time_ago = now - time_delta

            club_presence = await self.realm_club_get(guild_config["club_id"])
            if club_presence is None:
                # this can happen
                await ctx.reply(
                    "Seems like this command failed somehow. Astrea should have the "
                    + "info needed to see what's going on."
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
                )
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
                )
                await ctx.send(embed=first_embed)

                for chunk in chunks[1:]:
                    embed = nextcord.Embed(
                        colour=nextcord.Colour.lighter_gray(),
                        description="\n".join(chunk),
                    )
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
    async def online(self, ctx: commands.Context):
        """Allows you to see if anyone is online on the Realm right now.
        The realm must agree to this being enabled for you to use it."""
        # uses much of the same code as playerlist
        guild_config = self.bot.config[str(ctx.guild.id)]

        await ctx.reply("This might take quite a bit. Please be patient.")

        async with ctx.channel.typing():
            club_presence = await self.realm_club_get(guild_config["club_id"])
            if club_presence is None:
                # this can happen
                await ctx.reply(
                    "Seems like this command failed somehow. Astrea "
                    + "should have the info needed to see what's going on."
                )
                return

            player_list = await self.get_players_from_club_data(
                club_presence, online_only=True
            )

        online_list = [p.display for p in player_list]

        if online_list:
            embed = nextcord.Embed(
                colour=self.bot.color,
                title=f"{len(online_list)}/10 people online",
                description="\n".join(online_list),
            )
            await ctx.reply(embed=embed)
        else:
            raise utils.CustomCheckFailure("No one is on the Realm right now.")


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(Playerlist(bot))
