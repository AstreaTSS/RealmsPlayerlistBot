import asyncio
import datetime
import importlib
import typing
from enum import IntEnum

import aiohttp
import naff
import orjson

import common.playerlist_utils as pl_utils
import common.utils as utils


def _camel_to_const_snake(s):
    return "".join([f"_{c}" if c.isupper() else c.upper() for c in s]).lstrip("_")


hours_ago_choices = [
    naff.SlashCommandChoice("1", "1"),  # type: ignore
    naff.SlashCommandChoice("2", "2"),  # type: ignore
    naff.SlashCommandChoice("3", "3"),  # type: ignore
    naff.SlashCommandChoice("4", "4"),  # type: ignore
    naff.SlashCommandChoice("5", "5"),  # type: ignore
    naff.SlashCommandChoice("6", "6"),  # type: ignore
    naff.SlashCommandChoice("7", "7"),  # type: ignore
    naff.SlashCommandChoice("8", "8"),  # type: ignore
    naff.SlashCommandChoice("9", "9"),  # type: ignore
    naff.SlashCommandChoice("10", "10"),  # type: ignore
    naff.SlashCommandChoice("11", "11"),  # type: ignore
    naff.SlashCommandChoice("12", "12"),  # type: ignore
    naff.SlashCommandChoice("13", "13"),  # type: ignore
    naff.SlashCommandChoice("14", "14"),  # type: ignore
    naff.SlashCommandChoice("15", "15"),  # type: ignore
    naff.SlashCommandChoice("16", "16"),  # type: ignore
    naff.SlashCommandChoice("17", "17"),  # type: ignore
    naff.SlashCommandChoice("18", "18"),  # type: ignore
    naff.SlashCommandChoice("19", "19"),  # type: ignore
    naff.SlashCommandChoice("20", "20"),  # type: ignore
    naff.SlashCommandChoice("21", "21"),  # type: ignore
    naff.SlashCommandChoice("22", "22"),  # type: ignore
    naff.SlashCommandChoice("23", "23"),  # type: ignore
    naff.SlashCommandChoice("24", "24"),  # type: ignore
]


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


class ClubOnCooldown(Exception):
    def __init__(self) -> None:
        super().__init__("The club handler is on cooldown!")


class Playerlist(utils.Extension):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.sem = asyncio.Semaphore(
            3
        )  # prevents bot from overloading xbox api, hopefully
        self.club_sem = asyncio.Semaphore(10)

    async def _realm_club_json(
        self, club_id
    ) -> typing.Tuple[typing.Optional[dict], aiohttp.ClientResponse]:
        try:
            r = await self.bot.club.get_club_user_presences(club_id)
            if r.status == 429:
                # ratelimit, not much we can do here
                await asyncio.sleep(15)
                raise ClubOnCooldown()

            resp_json = await r.json(loads=orjson.loads)
            return resp_json, r
        except (aiohttp.ContentTypeError, ClubOnCooldown):
            async with self.bot.openxbl_session.get(
                f"https://xbl.io/api/v2/clubs/{club_id}"
            ) as r:
                try:
                    resp_json = await r.json(loads=orjson.loads)
                    return resp_json, r
                except aiohttp.ContentTypeError:
                    return None, r

    async def realm_club_get(self, club_id):
        async with self.club_sem:
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
        player_list: typing.List[pl_utils.Player] = []
        unresolved_dict: typing.Dict[str, pl_utils.Player] = {}

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

            player = pl_utils.Player(
                member["xuid"],
                last_seen,
                last_seen_state == ClubUserPresence.IN_GAME,
                await self.bot.redis.get(member["xuid"]),
            )
            if player.resolved:
                player_list.append(player)
            else:
                unresolved_dict[member["xuid"]] = player

        if unresolved_dict:
            gamertag_handler = pl_utils.GamertagHandler(
                self.bot,
                self.sem,
                tuple(unresolved_dict.keys()),
                self.bot.profile,
                self.bot.openxbl_session,
            )
            gamertag_dict = await gamertag_handler.run()

            for xuid, gamertag in gamertag_dict.items():
                unresolved_dict[xuid].gamertag = gamertag

            player_list.extend(unresolved_dict.values())

        return player_list

    @naff.slash_command(
        name="playerlist",
        description="Sends a playerlist, a log of players who have joined and left.",
        default_member_permissions=naff.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )  # type: ignore
    @naff.check(pl_utils.can_run_playerlist)  # type: ignore
    @naff.cooldown(naff.Buckets.GUILD, 1, 240)  # type: ignore
    @naff.slash_option("hours_ago", "How far back the playerlist should go.", naff.OptionTypes.STRING, choices=hours_ago_choices)  # type: ignore
    async def playerlist(
        self,
        ctx: utils.RealmContext | utils.RealmPrefixedContext,
        hours_ago: str = "12",
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

        actual_hours_ago: int = int(hours_ago)
        guild_config = await ctx.fetch_config()

        now = naff.Timestamp.utcnow()

        time_delta = datetime.timedelta(hours=actual_hours_ago)
        time_ago = now - time_delta

        club_presence = await self.realm_club_get(guild_config.club_id)
        if club_presence is None:
            # this can happen
            await ctx.send(
                "Seems like the playerlist command failed somehow. Astrea should "
                + "have the info needed to see what's going on."
            )
            return
        elif club_presence == "Unauthorized":
            await utils.msg_to_owner(self.bot, ctx.guild)
            await ctx.send(
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

        online_list = sorted(
            (p.display for p in player_list if p.in_game), key=lambda g: g.lower()
        )
        offline_list = tuple(p.display for p in player_list if not p.in_game)

        if online_list:
            embed = naff.Embed(
                color=self.bot.color,
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
            chunks = [offline_list[x : x + 40] for x in range(0, len(offline_list), 40)]

            first_embed = naff.Embed(
                color=naff.Color.from_hex("95a5a6"),
                description="\n".join(chunks[0]),
                title=f"People on in the last {actual_hours_ago} hour(s)",
                timestamp=now,
            )
            first_embed.set_footer(text="As of")
            await ctx.send(embed=first_embed)

            for chunk in chunks[1:]:
                embed = naff.Embed(
                    color=naff.Color.from_hex("95a5a6"),
                    description="\n".join(chunk),
                    timestamp=now,
                )
                embed.set_footer(text="As of")
                await ctx.send(embed=embed)
                await asyncio.sleep(0.2)

        if not kwargs.get("no_init_mes") and not online_list and not offline_list:
            raise utils.CustomCheckFailure(
                "No one has been on the Realm for the last "
                + f"{actual_hours_ago} hour(s)."
            )


def setup(bot):
    importlib.reload(utils)
    importlib.reload(pl_utils)
    Playerlist(bot)
