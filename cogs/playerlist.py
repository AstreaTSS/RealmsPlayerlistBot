import asyncio
import datetime
import importlib
import os
import typing

import aiohttp
import attr
import nextcord
from nextcord.ext import commands
from xbox.webapi.api.provider.profile.models import ProfileResponse

import common.profile_custom as profile
import common.utils as utils

"""
Hi, potential code viewer.
If you're looking at this, chances are you're interested in how this works.
I made this code a long time ago - it's June 21st 2021 right now, and I made it roughly a year before this.

Most of this code is not pretty and probably could be made better.
But at the same time, this code works, and poking around is not fun.
Also, this isn't exactly my favorite bot. I don't like messing around with this bot because I can't.
Oh well.

Also note that this code came from an old project called the Bappo Realm Bot
which is now defunct as that Realm is gone.
That bot had this, but it also had a much faster,
if more unstable playerlist that was used for the command version (this version was used
for the auto-run version).
Check it out here: https://github.com/Astrea49/BappoRealmBot/blob/master/cogs/cmds/playerlist.py
Though be warned that that version used a custom version of yet another API that communicated
directly with the Xbox Live API.

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

I'm going to attempt to leave comments and the like to document what I was doing
though note that I'm basically re-analyzing my own code to figure out what it all means.
I tend to make most of my code self-documenting, so it should be understandable enough,
but I may not be able to make you understand all of this.

Good luck on your bot coding journey
- Astrea
"""


class GamertagRecursionLimit(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Internal recursion limit reached. "
            + "Seems like fetching the gamertags failed. Astrea "
            + "should have the information to find out what's going on."
        )


@attr.s(slots=True, eq=False)
class Player:
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


async def can_run_playerlist(ctx: commands.Context):
    # simple check to see if a person can run the playerlist command
    guild_config = ctx.bot.config[str(ctx.guild.id)]
    return guild_config["club_id"] != "None"


async def can_run_online(ctx: commands.Context):
    # same, but for the online command
    guild_config = ctx.bot.config[str(ctx.guild.id)]
    return bool(guild_config["club_id"] != "None" and guild_config["online_cmd"])


class Playerlist(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.sem = asyncio.Semaphore(
            3
        )  # prevents bot from overloading xbox api, hopefully

    async def get_gamertags(
        self, profile: profile.ProfileProvider, list_xuids, limit=10,
    ) -> typing.Tuple[ProfileResponse, typing.List[str]]:

        profile_resp = await profile.get_profiles(list_xuids)
        profile_json = await profile_resp.json()

        if profile_json.get("code"):
            description: str = profile_json["description"]
            if description.startswith("Throttled"):
                limit -= 1
                if limit == 0:
                    await utils.msg_to_owner(
                        self.bot, f"Error: ```\n{profile_json}\n```"
                    )
                    raise GamertagRecursionLimit()

                await asyncio.sleep(5)
            else:
                desc_split = description.split(" ")
                list_xuids.remove(desc_split[1])

            profiles, list_xuids = await self.get_gamertags(profile, list_xuids, limit)
            return profiles, list_xuids

        elif profile_json.get("limitType"):
            limit -= 1
            if limit == 0:
                await utils.msg_to_owner(self.bot, f"Error: ```\n{profile_json}\n```")
                raise GamertagRecursionLimit()
            await asyncio.sleep(15)

            profiles, list_xuids = await self.get_gamertags(profile, list_xuids, limit)
            return profiles, list_xuids

        profiles = ProfileResponse.parse_obj(profile_json)
        return profiles, list_xuids

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

    @commands.command(aliases=["player_list", "get_playerlist", "get_player_list"])
    @utils.proper_permissions()
    @commands.check(can_run_playerlist)
    @commands.cooldown(1, 240, commands.BucketType.default)
    async def playerlist(self, ctx: commands.Context, **kwargs):
        """Checks and makes a playerlist, a log of players who have joined and left.
        The command version goes back 24 hours, while the autorun version only goes back 2.
        Has a cooldown of 4 minutes due to how intensive this command can be. May take a while to run at first.
        Requires Manage Server permissions."""
        guild_config = self.bot.config[str(ctx.guild.id)]

        if not kwargs.get("no_init_mes"):
            await ctx.reply("This might take quite a bit. Please be patient.")

        async with ctx.channel.typing():
            now = datetime.datetime.now(datetime.timezone.utc)

            limited = bool(kwargs.get("limited"))  # because python is weird

            if limited:
                time_delta = datetime.timedelta(hours=2)
            else:
                time_delta = datetime.timedelta(days=1)
            time_ago = now - time_delta

            # some initialization stuff
            player_list: typing.List[Player] = []  # hard to explain, you'll see
            unresolved_dict: typing.Dict[str, Player] = {}
            online_list: typing.List[str] = []  # stores currently on realm users
            offline_list: typing.List[str] = []  # stores recently online users
            club_presence = await self.realm_club_get(guild_config["club_id"])

            if club_presence is None:
                # this can happen
                await ctx.reply(
                    "Seems like this command failed somehow. Astrea should have the "
                    + "info needed to see what's going on."
                )
                return

            for member in club_presence:
                # xbox live uses a bit more precision than python can understand
                # so we cut out that precision
                last_seen = datetime.datetime.strptime(
                    member["lastSeenTimestamp"][:-2], "%Y-%m-%dT%H:%M:%S.%f"
                ).replace(tzinfo=datetime.timezone.utc)

                # if this person was on the realm longer than the time period specified
                # we can stop this for loop
                # useful as otherwise we would do an absurd number of requests getting every
                # single gamertag
                if last_seen <= time_ago:
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
                xuids = list(unresolved_dict.keys())

                for x in range(0, len(xuids), 50):
                    # limits how many gamertags we request for at once
                    xuids_to_get = xuids[x : x + 50]

                    async with self.sem:
                        profiles = await self.get_gamertags(
                            self.bot.profile, xuids_to_get
                        )

                        if xuids[-1] != xuids_to_get[-1]:
                            # ratelimits will complain otherwise
                            await asyncio.sleep(15)

                    for user in profiles[0].profile_users:
                        try:
                            gamertag = tuple(
                                s.value for s in user.settings if s.id == "Gamertag"
                            )[0]
                            self.bot.gamertags[user.id] = gamertag
                            unresolved_dict[user.id].gamertag = gamertag
                        except KeyError or IndexError:
                            continue

                player_list.extend(unresolved_dict.values())

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
                if (
                    len(offline_list) < 40
                ):  # if its bigger than this, we don't want to run into the chara limit

                    embed = nextcord.Embed(
                        colour=nextcord.Colour.lighter_gray(),
                        description="\n".join(offline_list),
                    )
                    if limited:
                        embed.title = "People on in the last 2 hours"
                    else:
                        embed.title = "People on in the last 24 hours"

                    await ctx.send(embed=embed)
                else:
                    # gets the offline list in lines of 40
                    # basically, it's like
                    # [ [list of 40 strings] [list of 40 strings] etc.]
                    # 40 lines can equal around 1400 characters, making this under, but safe
                    # note that in the worst case, it could be much more than 1400
                    chunks = [
                        offline_list[x : x + 40]
                        for x in range(0, len(offline_list), 40)
                    ]

                    embed_list = []

                    first_embed = nextcord.Embed(
                        colour=nextcord.Colour.lighter_gray(),
                        description="\n".join(chunks[0]),
                    )
                    if limited:
                        first_embed.title = "People on in the last 2 hours"
                    else:
                        first_embed.title = "People on in the last 24 hours"
                    embed_list.append(first_embed)

                    # bots can only send 10 embeds at a time
                    # so split them up by... 9's because we already added one
                    chunks = chunks[1:]
                    chunks_by_9 = [chunks[x : x + 9] for x in range(0, len(chunks), 9)]

                    for chunks in chunks_by_9:
                        for chunk in chunks:
                            embed = nextcord.Embed(
                                colour=nextcord.Colour.lighter_gray(),
                                description="\n".join(chunk),
                            )
                            embed_list.append(embed)

                        await ctx.send(embeds=embed_list)
                        embed_list.clear()
                        await asyncio.sleep(0.2)

        if not kwargs.get("no_init_mes"):
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

            online_list = []  # stores currently on realm users
            player_list: typing.List[Player] = []  # hard to explain, you'll see
            unresolved_dict: typing.Dict[str, Player] = {}

            for member in club_presence:
                if member["lastSeenState"] != "InGame":
                    break

                last_seen = datetime.datetime.strptime(
                    member["lastSeenTimestamp"][:-2], "%Y-%m-%dT%H:%M:%S.%f"
                ).replace(tzinfo=datetime.timezone.utc)

                player = Player(
                    member["xuid"],
                    last_seen,
                    member["lastSeenState"],
                    self.bot.gamertags.get(member["xuid"]),
                )
                if player.resolved:
                    player_list.append(player)
                else:
                    unresolved_dict[player.xuid] = player

            if unresolved_dict:
                async with self.sem:
                    profiles = await self.get_gamertags(
                        self.bot.profile, list(unresolved_dict.keys())
                    )

                for user in profiles[0].profile_users:
                    try:
                        gamertag = tuple(
                            s.value for s in user.settings if s.id == "Gamertag"
                        )[0]
                        self.bot.gamertags[user.id] = gamertag
                        unresolved_dict[user.id].gamertag = gamertag
                    except KeyError or IndexError:
                        continue

                player_list.extend(unresolved_dict.values())

        online_list = [p.display for p in player_list]

        if online_list:
            embed = nextcord.Embed(
                colour=self.bot.color,
                title=f"{len(online_list)}/10 people online",
                description="\n".join(online_list),
            )
            await ctx.reply(embed=embed)
        else:
            raise utils.CustomCheckFailure("There's no one on the Realm right now!")


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(Playerlist(bot))
