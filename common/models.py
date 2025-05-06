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

import logging
import os
import re
from datetime import UTC, datetime, timedelta
from functools import cached_property

import orjson
import typing_extensions as typing
from tortoise import Model, fields
from tortoise.contrib.postgres.fields import ArrayField

logger = logging.getLogger("realms_bot")

USER_MENTION = re.compile(r"^<@!?[0-9]{15,25}>$")


def display_gamertag(
    xuid: str, gamertag: str | None = None, nickname: str | None = None
) -> str:
    display = "Unknown User"
    if nickname:
        # optional check to display user mentions as is if it is one
        display = nickname if USER_MENTION.fullmatch(nickname) else f"`{nickname}`"
    elif gamertag:
        display = f"`{gamertag}`"
    elif xuid:
        display = f"User with XUID `{xuid}`"

    return display


class NotificationChannels(typing.TypedDict, total=False):
    realm_offline: int
    player_watchlist: int
    reoccurring_leaderboard: int


class GuildConfig(Model):
    guild_id = fields.BigIntField(primary_key=True, source_field="guild_id")
    club_id: fields.Field[typing.Optional[str]] = fields.CharField(
        max_length=50, null=True, source_field="club_id"
    )
    playerlist_chan: fields.Field[typing.Optional[int]] = fields.BigIntField(
        source_field="playerlist_chan"
    )
    realm_id: fields.Field[typing.Optional[str]] = fields.CharField(
        max_length=50, null=True, source_field="realm_id"
    )
    live_playerlist = fields.BooleanField(default=False, source_field="live_playerlist")
    realm_offline_role: fields.Field[typing.Optional[int]] = fields.BigIntField(
        source_field="realm_offline_role", null=True
    )
    warning_notifications = fields.BooleanField(
        default=True, source_field="warning_notifications"
    )
    fetch_devices = fields.BooleanField(default=False, source_field="fetch_devices")
    live_online_channel: fields.Field[typing.Optional[str]] = fields.CharField(
        max_length=75, null=True, source_field="live_online_channel"
    )
    player_watchlist_role: fields.Field[typing.Optional[int]] = fields.BigIntField(
        source_field="player_watchlist_role", null=True
    )
    player_watchlist: fields.Field[list[str] | None] = ArrayField(
        "TEXT", null=True, source_field="player_watchlist"
    )
    notification_channels: fields.Field[NotificationChannels] = fields.JSONField(
        default="{}",
        source_field="notification_channels",
        encoder=lambda x: orjson.dumps(x).decode(),
        decoder=orjson.loads,
    )
    reoccurring_leaderboard: fields.Field[typing.Optional[int]] = fields.IntField(
        source_field="reoccurring_leaderboard", null=True
    )
    nicknames = fields.JSONField(default="{}", source_field="nicknames")

    premium_code: fields.ForeignKeyNullableRelation["PremiumCode"] = (
        fields.ForeignKeyField(
            "models.PremiumCode",
            related_name="guilds",
            on_delete=fields.SET_NULL,
            null=True,
        )
    )

    class Meta:
        table = "realmguildconfig"

    @cached_property
    def valid_premium(self) -> bool:
        return bool(self.premium_code and self.premium_code.valid_code)

    def get_notif_channel(self, type_name: str) -> int:
        return self.notification_channels.get(type_name, self.playerlist_chan)


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


class PlayerSession(Model):
    custom_id = fields.UUIDField(primary_key=True, source_field="custom_id")
    realm_id = fields.CharField(max_length=50, source_field="realm_id")
    xuid = fields.CharField(max_length=50, source_field="xuid")
    online = fields.BooleanField(default=False, source_field="online")
    last_seen = fields.DatetimeField(source_field="last_seen")
    joined_at: fields.Field[typing.Optional[datetime]] = fields.DatetimeField(
        null=True, source_field="joined_at"
    )

    gamertag: typing.Optional[str] = None
    device: typing.Optional[str] = None
    show_left: bool = True

    class Meta:
        table = "realmplayersession"

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
                logger.info("Unknown device: %s", self.device)
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

    def base_display(self, nickname: str | None = None) -> str:
        display = display_gamertag(self.xuid, self.gamertag, nickname)
        if self.device_emoji:
            display += f" {self.device_emoji}"
        return display

    def display(self, nickname: str | None = None) -> str:
        notes: list[str] = []
        if self.joined_at:
            notes.append(f"joined <t:{int(self.joined_at.timestamp())}:f>")

        if not self.online and self.show_left:
            notes.append(f"left <t:{int(self.last_seen.timestamp())}:f>")

        return (
            f"{self.base_display(nickname)}: {', '.join(notes)}"
            if notes
            else self.base_display(nickname)
        )


class PremiumCode(Model):
    id = fields.IntField(primary_key=True, source_field="id")
    code = fields.CharField(max_length=100, source_field="code")
    user_id: fields.Field[typing.Optional[int]] = fields.BigIntField(
        source_field="user_id", null=True
    )
    uses = fields.IntField(default=0, source_field="uses")
    max_uses = fields.IntField(default=2, source_field="max_uses")
    customer_id: fields.Field[typing.Optional[str]] = fields.CharField(
        max_length=50, null=True, source_field="customer_id"
    )
    expires_at: fields.Field[typing.Optional[datetime]] = fields.DatetimeField(
        null=True, source_field="expires_at"
    )

    guilds: fields.ReverseRelation["GuildConfig"]

    _valid_code: bool | None = None

    class Meta:
        table = "realmpremiumcode"

    @property
    def valid_code(self) -> bool:
        if self._valid_code is not None:
            return self._valid_code
        self._valid_code = not self.expires_at or self.expires_at + timedelta(
            days=1
        ) > datetime.now(UTC)
        return self._valid_code
