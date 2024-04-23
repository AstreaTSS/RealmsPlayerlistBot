"""
Copyright 2020-2024 AstreaTSS.
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

import typing
from datetime import datetime

import attrs
import interactions as ipy

import common.models as models
import common.playerlist_utils as pl_utils


@typing.dataclass_transform(
    eq_default=False,
    order_default=False,
    kw_only_default=False,
    field_specifiers=(attrs.field,),
)
def define[C]() -> typing.Callable[[C], C]:
    return attrs.define(eq=False, order=False, hash=False, kw_only=False)  # type: ignore


@define()
class PlayerlistParseFinish(ipy.events.BaseEvent):
    containers: tuple[pl_utils.RealmPlayersContainer, ...] = attrs.field(repr=False)


@define()
class PlayerlistEvent(ipy.events.BaseEvent):
    realm_id: str = attrs.field(repr=False)

    async def configs(self) -> list[models.GuildConfig]:
        return await models.GuildConfig.prisma().find_many(
            where={"realm_id": self.realm_id}
        )


@define()
class RealmDown(PlayerlistEvent):
    disconnected: set[str] = attrs.field(repr=False)
    timestamp: datetime = attrs.field(repr=False)


@define()
class LivePlayerlistSend(PlayerlistEvent):
    joined: set[str] = attrs.field(repr=False)
    left: set[str] = attrs.field(repr=False)
    timestamp: datetime = attrs.field(repr=False)
    realm_down_event: bool = attrs.field(repr=False, default=False, kw_only=True)


@define()
class LiveOnlineUpdate(LivePlayerlistSend):
    gamertag_mapping: dict[str, str] = attrs.field(repr=False)
    config: models.GuildConfig = attrs.field(repr=False)

    @property
    def live_online_channel(self) -> str:
        return self.config.live_online_channel  # type: ignore


@define()
class WarnMissingPlayerlist(PlayerlistEvent):
    pass


@define()
class PlayerWatchlistMatch(PlayerlistEvent):
    player_xuid: str = attrs.field(repr=False)
    guild_ids: set[int] = attrs.field(repr=False)

    async def configs(self) -> list[models.GuildConfig]:
        return await models.GuildConfig.prisma().find_many(
            where={"realm_id": self.realm_id, "guild_id": {"in": list(self.guild_ids)}}
        )
