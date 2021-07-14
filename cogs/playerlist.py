import datetime
import importlib
import os

import aiohttp
from discord.ext import commands
from discord.ext import tasks

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
Check it out here: https://github.com/Sonic4999/BappoRealmBot/blob/master/cogs/cmds/playerlist.py
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
- Sonic49
"""


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

    async def gamertag_handler(self, xuid):
        # easy way of handling getting a gamertag from an xuid
        # as the clubs request does not get gamertags itself

        # this is where the gamertag cache that the bot has comes into use
        # the bot stores gamertags in an {xuid: gamertag} format
        # which is useful if we dont want to overload the api we're using
        # with requests over and over again
        # since we do have to determine the gamertag from xuid a lot

        # note that there is a flaw in this system: gamertags will never update for an xuid
        # unless manually cleared
        # this is fine for most use cases, but you may want to implement a system that gets
        # rid of gamertags if theyve been stored over a long period of time

        # use strings here because xbox live api is weird
        if str(xuid) in self.bot.gamertags.keys():
            return self.bot.gamertags[str(xuid)]

        # we use https://xbl.io/ for communicating with the xbox live api
        # why? because the actual xbox live api sucks and is hard to use
        # this service makes that way easier
        headers = {
            "X-Authorization": os.environ.get("OPENXBL_KEY"),
            "Accept": "application/json",
            "Accept-Language": "en-US",
        }

        # don't ask
        xuid = str(xuid).replace("'", "")

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"https://xbl.io/api/v2/account/{xuid}") as r:
                try:
                    resp_json = (
                        await r.json()
                    )  # i have little idea of how this looks these days - experiment yourself
                    if "code" in resp_json.keys():  # service is down
                        await utils.msg_to_owner(self.bot, resp_json)
                        return f"User with xuid {xuid}"
                    else:
                        # xbox does this annoying thing where it maps out all of the 'settings'
                        # (settings are just basic info about the user, don't ask)
                        # in an {"id": "e", "value": "f"} format
                        # why isn't it just {"e": "f"}? idk

                        # also for some reason the xbox live api gives every response as a list
                        # even when we're only requesting for one person
                        settings = {
                            setting["id"]: setting["value"]
                            for setting in resp_json["profileUsers"][0]["settings"]
                        }

                        gamertag = settings["Gamertag"]  # where the gamertag is stored
                        # probably would be easier to manually just get it, but eh

                        self.bot.gamertags[str(xuid)] = gamertag  # add to cache
                        return gamertag
                except aiohttp.client_exceptions.ContentTypeError:
                    # can happen, if not rare
                    await utils.msg_to_owner(
                        self.bot, f"Failed to get gamertag of user {xuid}"
                    )
                    return f"User with xuid {xuid}"

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
                except KeyError:
                    # who knows
                    await utils.msg_to_owner(self.bot, resp_json)
                    await utils.msg_to_owner(self.bot, r.headers)
                    await utils.msg_to_owner(self.bot, r.status)
                    return None

    @commands.command(aliases=["player_list", "get_playerlist", "get_player_list"])
    @utils.proper_permissions()
    @commands.cooldown(1, 240, commands.BucketType.default)
    async def playerlist(self, ctx: commands.Context, **kwargs):
        """Checks and makes a playerlist, a log of players who have joined and left.
        The command version goes back 24 hours, while the autorun version only goes back 2.
        Has a cooldown of 4 minutes due to how intensive this command can be. May take a while to run at first.
        Requires Manage Server permissions."""
        guild_config = self.bot.config[str(ctx.guild.id)]

        if guild_config["club_id"] == "None":
            raise commands.BadArgument(
                "This server is not ready to use playerlist yet."
            )

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
            online_list = []  # stores currently on realm users
            offline_list = (
                []
            )  # stores users who were on the realm in the time period specified
            club_presence = await self.realm_club_get(guild_config["club_id"])

            if club_presence is None:
                # this can happen
                await ctx.send(
                    "Seems like this command failed somehow. Sonic should have the info needed to see what's going on."
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

                # yeah, we only get the xuid from this list
                # xuids are basically xbox's equivalent of discord ids
                # but they dont give us info on gamertags
                # so the below function is just for that
                gamertag = await self.gamertag_handler(member["xuid"])
                if (
                    member["lastSeenState"] == "InGame"
                ):  # the state that indicates they're in game
                    online_list.append(f"`{gamertag}`")
                else:
                    # screw manually doing this, let discord handle it
                    time_format = f"<t:{int(last_seen.timestamp())}>"
                    offline_list.append(f"`{gamertag}`: last seen {time_format}")

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
    async def online(self, ctx: commands.Context):
        """Allows you to see if anyone is online on the Realm right now.
        The realm must agree to this being enabled for you to use it."""

        guild_config = self.bot.config[str(ctx.guild.id)]
        if guild_config["club_id"] == "None" or not guild_config["online_cmd"]:
            raise commands.BadArgument(
                "This server is not allowed to use this command."
            )

        if self.bot.gamertags == {}:
            await ctx.send(
                "This will probably take a long time as the bot does not have a gamertag cache. Please be patient."
            )
            # it can take up to a minute on its first run
        else:
            await ctx.send("This might take a bit. Please be patient.")

        club_presence = await self.realm_club_get(guild_config["club_id"])

        if club_presence is None:
            # this can happen
            await ctx.send(
                "Seems like this command failed somehow. The owner of the bot "
                + "should have the info needed to see what's going on."
            )
            return

        online_list = []  # stores currently on realm users

        for member in club_presence:
            if member["lastSeenState"] != "InGame":
                break

            gamertag = await self.gamertag_handler(member["xuid"])
            online_list.append(f"`{gamertag}`")

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
