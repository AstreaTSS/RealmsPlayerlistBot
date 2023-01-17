import asyncio
import datetime
import typing
from enum import IntEnum

import aiohttp
import orjson

import common.models as models
import common.utils as utils
from common.microsoft_core import MicrosoftAPIException


def _camel_to_const_snake(s: str) -> str:
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
    def from_xbox_api(cls, value: str) -> typing.Self:
        try:
            return cls[_camel_to_const_snake(value)]
        except KeyError:
            # it's not like i forgot a value, it's just that some are
            # literally not documented
            return cls.UNKNOWN


class ClubOnCooldown(Exception):
    def __init__(self) -> None:
        super().__init__("The club handler is on cooldown!")


async def _realm_club_json(
    bot: utils.RealmBotBase, club_id: str
) -> tuple[typing.Optional[dict], typing.Optional[aiohttp.ClientResponse]]:
    try:
        resp_json = await bot.xbox.fetch_club_presences(club_id)

        if resp_json.get("limitType"):
            # ratelimit, not much we can do here
            if seconds := resp_json.get("periodInSeconds"):
                await asyncio.sleep(int(seconds))
            else:
                await asyncio.sleep(15)
            raise ClubOnCooldown()

        return resp_json, None
    except (MicrosoftAPIException, ClubOnCooldown):
        async with bot.openxbl_session.get(
            f"https://xbl.io/api/v2/clubs/{club_id}"
        ) as r:
            try:
                resp_json = await r.json(loads=orjson.loads)

                if resp_json.get("limitType"):
                    # ratelimit, not much we can do here
                    if seconds := resp_json.get("periodInSeconds"):
                        await asyncio.sleep(int(seconds))
                    else:
                        await asyncio.sleep(15)

                    return await _realm_club_json(bot, club_id)

                return resp_json, r
            except aiohttp.ContentTypeError:
                return None, r


async def realm_club_get(bot: utils.RealmBotBase, club_id: str) -> typing.Any:
    resp_json, resp = await _realm_club_json(bot, club_id)

    if not resp_json:
        if typing.TYPE_CHECKING:
            assert resp is not None  # noqa: S101

        resp_text = await resp.text()
        await utils.msg_to_owner(bot, resp_text)
        await utils.msg_to_owner(bot, resp.headers)
        await utils.msg_to_owner(bot, resp.status)
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

        await utils.msg_to_owner(bot, resp_json)
        if resp:
            await utils.msg_to_owner(bot, resp.headers)
            await utils.msg_to_owner(bot, resp.status)
        return None


async def get_players_from_club_data(
    bot: utils.RealmBotBase,
    realm_id: str,
    club_id: str,
    time_ago: datetime.datetime,
) -> list[models.PlayerSession] | None:
    club_presence = await realm_club_get(bot, club_id)
    if not club_presence or club_presence == "Unauthorized":
        return None

    now = datetime.datetime.now(tz=datetime.UTC)
    player_list: list[models.PlayerSession] = []

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

        # xbox live uses a bit more precision than python can understand
        # so we cut out that precision
        last_seen = datetime.datetime.strptime(
            member["lastSeenTimestamp"][:-2], "%Y-%m-%dT%H:%M:%S.%f"
        ).replace(tzinfo=datetime.UTC)

        # if this person was on the realm longer than the time period specified
        # we can stop this for loop
        # useful as otherwise we would do an absurd number of requests getting every
        # single gamertag
        if last_seen <= time_ago:
            break

        online = last_seen_state == ClubUserPresence.IN_GAME
        player_list.append(
            models.PlayerSession(
                custom_id=bot.uuid_cache[f"{realm_id}-{member['xuid']}"],
                realm_id=realm_id,
                xuid=member["xuid"],
                online=online,
                last_seen=now if online else last_seen,
            )
        )
        bot.online_cache[int(realm_id)].add(member["xuid"])

    return player_list


async def fill_in_data_from_clubs(
    bot: utils.RealmBotBase,
    realm_id: str,
    club_id: str,
) -> None:
    time_ago = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=24)
    player_list = await get_players_from_club_data(bot, realm_id, club_id, time_ago)

    if not player_list:
        return

    await models.PlayerSession.bulk_create(
        player_list,
        on_conflict=("custom_id",),
        update_fields=("online", "last_seen"),
    )
