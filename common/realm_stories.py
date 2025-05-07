"""
Copyright 2020-2025 AstreaTSS.
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

import datetime
import typing

import elytra

import common.models as models
import common.utils as utils


def get_floored_minute_timestamp(
    d: datetime.datetime,
) -> datetime.datetime:
    kwargs: dict[str, typing.Any] = {
        "second": 0,
        "microsecond": 0,
        "tzinfo": datetime.UTC,
    }
    return d.replace(**kwargs)


async def fill_in_data_from_stories(
    bot: utils.RealmBotBase,
    realm_id: str,
) -> bool:
    close_to_now = get_floored_minute_timestamp(datetime.datetime.now(tz=datetime.UTC))

    try:
        await bot.realms.update_realm_story_settings(
            realm_id, player_opt_in="OPT_IN", timeline=True
        )
        resp = await bot.realms.fetch_realm_story_player_activity(realm_id)
    except elytra.MicrosoftAPIException:
        return False

    if not resp.activity:
        return False

    player_list: list[models.PlayerSession] = []

    for xuid, entries in resp.activity.items():
        for entry in entries:
            end_floored = get_floored_minute_timestamp(entry.end)
            start_floored = get_floored_minute_timestamp(entry.start)

            online = close_to_now <= end_floored

            player_list.append(
                models.PlayerSession(
                    custom_id=bot.uuid_cache[f"{realm_id}-{xuid}"],
                    realm_id=realm_id,
                    xuid=xuid,
                    online=online,
                    last_seen=close_to_now if online else end_floored,
                    joined_at=start_floored,
                )
            )

            if online:
                bot.online_cache[int(realm_id)].add(xuid)

    if player_list:
        await models.PlayerSession.bulk_create(player_list, ignore_conflicts=True)
    return True
