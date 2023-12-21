"""
Copyright 2020-2023 AstreaTSS.
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

import logging
import os
import typing
from datetime import UTC, datetime, timedelta
from functools import cached_property

from prisma import Json

# i cannot tell you just how ridiculous this seems
# prisma generates models on the fly??? just for typehinting???
# i love it
from prisma.models import (
    GuildConfig as PrismaGuildConfig,
)
from prisma.models import (
    PlayerSession as PrismaPlayerSession,
)
from prisma.models import (
    PremiumCode as PrismaPremiumCode,
)

logger = logging.getLogger("realms_bot")


class IgnoreModel:
    __slots__ = ()
    # problem: prisma reads every field in the model and adds them to a set of things to query
    # this includes our virtual fields, which are not in the database
    # solution: prisma ignores fields that are typehinted as their own type of model,
    # and it detects it through the existence of this property, so here we are
    __prisma_model__ = "IgnoreModel"


class NotificationChannels(typing.TypedDict, total=False):
    realm_offline: int
    player_watchlist: int
    reoccurring_leaderboard: int


class GuildConfig(PrismaGuildConfig):
    if typing.TYPE_CHECKING:
        notification_channels: NotificationChannels

    premium_code: typing.Optional["PremiumCode"] = None

    @classmethod
    async def get(cls, guild_id: int) -> "GuildConfig":
        return await cls.prisma().find_unique_or_raise(
            where={"guild_id": guild_id}, include={"premium_code": True}
        )

    @classmethod
    async def get_or_none(cls, guild_id: int) -> typing.Optional["GuildConfig"]:
        return await cls.prisma().find_unique(
            where={"guild_id": guild_id}, include={"premium_code": True}
        )

    @cached_property
    def valid_premium(self) -> bool:
        return bool(self.premium_code and self.premium_code.valid_code)

    async def save(self) -> None:
        data = self.model_dump(exclude={"premium_code_id", "premium_code"})
        if data.get("notification_channels") is not None:
            data["notification_channels"] = Json(data["notification_channels"])
        await self.prisma().update(where={"guild_id": self.guild_id}, data=data)  # type: ignore


EMOJI_DEVICE_NAMES = {
    "Android": "android",
    "iOS": "ios",
    "WindowsOneCore": "windows",
    "Win32": "windows",
    "XboxOne": "xbox_one",
    "Scarlett": "xbox_series",
    "Xbox360": "xbox_360",  # what?
    "Nintendo": "switch",
    "PlayStation": "playstation",
}


class PlayerSession(PrismaPlayerSession):
    if typing.TYPE_CHECKING:
        gamertag: typing.Optional[str] = None
        device: typing.Optional[str] = None
        show_left: bool = True
    else:
        gamertag: typing.Optional[IgnoreModel] = None
        device: typing.Optional[IgnoreModel] = None
        show_left: IgnoreModel | bool = True

    @property
    def device_emoji(self) -> str | None:
        if not self.device:
            return None

        # case statement, woo!
        match self.device:
            case "Android":
                base_emoji_id = os.environ["ANDROID_EMOJI_ID"]
            case "iOS":
                base_emoji_id = os.environ["IOS_EMOJI_ID"]
            case "WindowsOneCore" | "Win32":
                base_emoji_id = os.environ["WINDOWS_EMOJI_ID"]
            case "XboxOne" | "Xbox360":
                base_emoji_id = os.environ["XBOX_ONE_EMOJI_ID"]
            case "Scarlett":
                base_emoji_id = os.environ["XBOX_SERIES_EMOJI_ID"]
            case "Nintendo":
                base_emoji_id = os.environ["SWITCH_EMOJI_ID"]
            case "PlayStation":
                base_emoji_id = os.environ["PLAYSTATION_EMOJI_ID"]
            case _:
                logger.info(f"Unknown device: {self.device}")
                base_emoji_id = os.environ["UNKNOWN_DEVICE_EMOJI_ID"]

        return (
            f"<:{EMOJI_DEVICE_NAMES.get(self.device, self.device.lower().replace(' ', '_'))}:{base_emoji_id}>"
        )

    @property
    def realm_xuid_id(self) -> str:
        return f"{self.realm_id}-{self.xuid}"

    @property
    def resolved(self) -> bool:
        return bool(self.gamertag)

    @property
    def base_display(self) -> str:
        display = "Unknown User"
        if self.gamertag:
            display = f"`{self.gamertag}`"
        elif self.xuid:
            display = f"User with XUID `{self.xuid}`"

        if self.device_emoji:
            display += f" ({self.device_emoji})"
        return display

    @property
    def display(self) -> str:
        notes: list[str] = []
        if self.joined_at:
            notes.append(f"joined <t:{int(self.joined_at.timestamp())}:f>")

        if not self.online and self.show_left:
            notes.append(f"left <t:{int(self.last_seen.timestamp())}:f>")

        return (
            f"{self.base_display}: {', '.join(notes)}" if notes else self.base_display
        )


class PremiumCode(PrismaPremiumCode):
    if typing.TYPE_CHECKING:
        _valid_code: bool | None = None
    else:
        _valid_code: IgnoreModel | None = None

    @property
    def valid_code(self) -> bool:
        if self._valid_code is not None:
            return self._valid_code
        self._valid_code = not self.expires_at or self.expires_at + timedelta(
            days=1
        ) > datetime.now(UTC)
        return self._valid_code


GuildConfig.model_rebuild(force=True)
