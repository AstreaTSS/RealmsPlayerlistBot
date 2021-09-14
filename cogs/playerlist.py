import asyncio
import datetime
import importlib
import os
import typing

import aiohttp
import attr
from discord.ext import commands
from discord.ext import tasks
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
            time_format = f"<t:{int(self.last_seen.timestamp())}>"
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
        self.bot = bot
        self.playerlist_loop.start()

    def cog_unload(self):
        self.playerlist_loop.cancel()

    @tasks.loop(hours=1)
    async def playerlist_loop(self):
        """A simple way of running the playerlist command every hour in every server the bot is in.
        Or, at least, in every server that's listed in the config. See `config.json` for that.
        See `cogs.config_fetch` for how the bot gets the config from that file."""

        for guild_id in self.bot.config.keys():
            guild_config = self.bot.config[guild_id]

            if (
                guild_config["club_id"] != "None"
            ):  # probably could have done a null value, but old code go brr
                chan = self.bot.get_channel(
                    guild_config["playerlist_chan"]
                )  # playerlist channel
                list_cmd = self.bot.get_command("playerlist")

                # gets the most recent message in the playerlist channel
                # it used to fetch a specific message from there, but honestly, this method is better
                messages = await chan.history(limit=1).flatten()
                a_ctx = await self.bot.get_context(messages[0])

                # take advantage of the fact that users cant really use kwargs for commands
                # the two listed here silence the 'this may take a long time' message
                # and also make it so it doesnt go back 24 hours, instead only going two
                await a_ctx.invoke(list_cmd, no_init_mes=True, limited=True)

    @playerlist_loop.error
    async def error_handle(self, *args):
        error = args[-1]
        await utils.error_handle(self.bot, error)

    async def get_gamertags(
        self, profile: profile.ProfileProvider, list_xuids
    ) -> ProfileResponse:

        profile_resp = await profile.get_profiles(list_xuids)

        if profile_resp.get("code"):
            description = profile_resp["description"]
            desc_split = description.split(" ")
            list_xuids.remove(desc_split[1])

            profiles, list_xuids = await self.get_gamertags(profile, list_xuids)
            return profiles, list_xuids

        elif profile_resp.get("limitType"):
            await asyncio.sleep(15)
            profiles, list_xuids = await self.get_gamertags(profile, list_xuids)
            return profiles, list_xuids

        profiles = ProfileResponse.parse_raw(await profile_resp.text())
        return profiles, list_xuids

    async def realm_club_get(self, club_id):
        headers = {  # same api as the gamerag one
            "X-Authorization": os.environ.get("OPENXBL_KEY"),
            "Accept": "application/json",
            "Accept-Language": "en-US",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"https://xbl.io/api/v2/clubs/" + club_id) as r:
                resp_json = await r.json()

                try:
                    # again, the xbox live api gives every response as a list
                    # even when requesting for one thing
                    # and we only need the presences of the users
                    # not the other stuff
                    return resp_json["clubs"][0]["clubPresence"]
                except KeyError or TypeError:
                    # who knows
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
            if self.bot.gamertags == {}:
                await ctx.send(
                    "This will probably take a long time as the bot does not have a gamertag cache. Please be patient."
                )
                # it can take up to a minute on its first run
            else:
                await ctx.send("This might take a bit. Please be patient.")

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
            online_list: typing.List[Player] = []  # stores currently on realm users
            offline_list: typing.List[Player] = []  # stores recently online users
            club_presence = await self.realm_club_get(guild_config["club_id"])

            if club_presence is None:
                # this can happen
                await ctx.send(
                    "Seems like this command failed somehow. Astrea should have the info needed to see what's going on."
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
                    unresolved_dict(player)

            if unresolved_dict:
                client_profile = self.bot.profile

                profiles = await self.get_gamertags(
                    client_profile, list(unresolved_dict.keys())
                )
                for user in profiles.profile_users:
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
            online_str = "**People online right now:**\n\n" + "\n".join(online_list)
            await ctx.send(online_str)

        if offline_list:
            if (
                len(offline_list) < 20
            ):  # if its bigger than this, we don't want to run into the chara limit
                if limited:
                    offline_str = "**Other people on in the last 2 hours:**\n\n"

                else:
                    offline_str = "**Other people on in the last 24 hours:**\n\n"
                offline_str += "\n".join(offline_list)
                await ctx.send(offline_str)
            else:
                # gets the offline list in lines of 20
                # basically, it's like
                # [ [list of 20 strings] [list of 20 strings] etc.]
                chunks = [
                    offline_list[x : x + 20] for x in range(0, len(offline_list), 20)
                ]

                if limited:
                    first_offline_str = (
                        "**Other people on in the last 2 hours:**\n\n"
                        + "\n".join(chunks[0])
                    )

                else:
                    first_offline_str = (
                        "**Other people on in the last 24 hours:**\n\n"
                        + "\n".join(chunks[0])
                    )
                await ctx.send(first_offline_str)

                for chunk in chunks[1:]:
                    offline_chunk_str = "\n".join(chunk)
                    await ctx.send(offline_chunk_str)

    @commands.command()
    @commands.cooldown(1, 300, commands.BucketType.guild)
    @commands.check(can_run_online)
    async def online(self, ctx: commands.Context):
        """Allows you to see if anyone is online on the Realm right now.
        The realm must agree to this being enabled for you to use it."""
        # uses much of the same code as playerlist
        guild_config = self.bot.config[str(ctx.guild.id)]

        if self.bot.gamertags == {}:
            await ctx.send(
                "This will probably take a long time as the bot does not have a gamertag cache. Please be patient."
            )
            # it can take up to a minute on its first run
        else:
            await ctx.send("This might take a bit. Please be patient.")

        async with ctx.channel.typing():
            club_presence = await self.realm_club_get(guild_config["club_id"])

            if club_presence is None:
                # this can happen
                await ctx.send(
                    "Seems like this command failed somehow. The owner of the bot "
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
                profiles = await self.get_gamertags(
                    self.bot.profile, list(unresolved_dict.keys())
                )
                for user in profiles.profile_users:
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
            online_str = f"**{len(online_list)}/10 people online:**\n\n" + "\n".join(
                online_list
            )
            await ctx.send(online_str)
        else:
            raise utils.CustomCheckFailure("There's no one on the Realm right now!")


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(Playerlist(bot))
