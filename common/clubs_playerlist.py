import asyncio
import datetime
import typing

import aiohttp
import elytra
import orjson
from msgspec import ValidationError

import common.models as models
import common.utils as utils


async def realm_club_presence(
    bot: utils.RealmBotBase, club_id: str
) -> typing.Optional[elytra.ClubResponse]:
    try:
        return await bot.xbox.fetch_club_presence(club_id)
    except elytra.MicrosoftAPIException as e:
        if e.resp in {400, 403}:
            return None

        resp = await bot.openxbl_session.get(f"https://xbl.io/api/v2/clubs/{club_id}")
        try:
            resp_bytes = await resp.read()
            resp_json = orjson.loads(resp_bytes)

            if resp_json.get("limitType"):
                # ratelimit, not much we can do here
                if seconds := resp_json.get("periodInSeconds"):
                    await asyncio.sleep(int(seconds))
                else:
                    await asyncio.sleep(5)

                return await realm_club_presence(bot, club_id)

            return elytra.ClubResponse.from_bytes(resp_bytes)
        except (aiohttp.ContentTypeError, orjson.JSONDecodeError, ValidationError):
            return None


async def realm_club_get(
    bot: utils.RealmBotBase, club_id: str
) -> list[elytra.ClubPresence] | None:
    club_resp = await realm_club_presence(bot, club_id)

    if not club_resp:
        return None

    try:
        return club_resp.clubs[0].club_presence
    except (KeyError, TypeError, ValidationError):
        # who knows x2
        return None


async def get_players_from_club_data(
    bot: utils.RealmBotBase,
    realm_id: str,
    club_id: str,
    time_ago: datetime.datetime,
) -> list[models.PlayerSession] | None:
    club_presence = await realm_club_get(bot, club_id)
    if not club_presence:
        return None

    now = datetime.datetime.now(tz=datetime.UTC)
    player_list: list[models.PlayerSession] = []

    for member in club_presence:
        last_seen_state = member.last_seen_state

        if last_seen_state not in {
            elytra.ClubUserPresence.IN_GAME,
            elytra.ClubUserPresence.NOT_IN_CLUB,
        }:
            # we want to ignore people causally browsing the club itself
            # this isn't perfect, as if they stop viewing the club, they'll be put in
            # the "NotInClub" list, but that's fine
            continue

        # xbox live uses a bit more precision than python can understand
        # so we cut out that precision
        last_seen = member.last_seen_timestamp.replace(tzinfo=datetime.UTC)

        # if this person was on the realm longer than the time period specified
        # we can stop this for loop
        # useful as otherwise we would do an absurd number of requests getting every
        # single gamertag
        if last_seen <= time_ago:
            break

        online = last_seen_state == elytra.ClubUserPresence.IN_GAME
        player_list.append(
            models.PlayerSession(
                custom_id=bot.uuid_cache[f"{realm_id}-{member.xuid}"],
                realm_id=realm_id,
                xuid=member.xuid,
                online=online,
                last_seen=now if online else last_seen,
            )
        )
        bot.online_cache[int(realm_id)].add(member.xuid)

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
