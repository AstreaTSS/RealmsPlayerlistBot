import logging
import os
import typing
from datetime import UTC, datetime
from functools import cached_property
from uuid import UUID

from tortoise import fields
from tortoise.models import Model

logger = logging.getLogger("realms_bot")


class GuildConfig(Model):
    class Meta:
        table = "realmguildconfig"

    guild_id: int = fields.BigIntField(pk=True)
    club_id: typing.Optional[str] = fields.CharField(50, null=True)
    playerlist_chan: typing.Optional[int] = fields.BigIntField(null=True)
    realm_id: typing.Optional[str] = fields.CharField(50, null=True)
    live_playerlist: bool = fields.BooleanField(default=False)  # type: ignore
    realm_offline_role: typing.Optional[int] = fields.BigIntField(null=True)
    warning_notifications: bool = fields.BooleanField(default=True)  # type: ignore
    fetch_devices: bool = fields.BooleanField(default=False)  # type: ignore
    live_online_channel: typing.Optional[str] = fields.CharField(75, null=True)  # type: ignore
    premium_code: fields.ForeignKeyNullableRelation[
        "PremiumCode"
    ] = fields.ForeignKeyField(
        "models.PremiumCode",
        related_name="guilds",
        on_delete=fields.SET_NULL,
        null=True,
    )  # type: ignore

    @cached_property
    def valid_premium(self) -> bool:
        return bool(
            self.premium_code
            and (
                not self.premium_code.expires_at
                or self.premium_code.expires_at > datetime.now(UTC)
            )
        )


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
    class Meta:
        # pro tip: this table REALLY needs a good index for bigger instances -
        # something i cant do automatically here through tortoise
        # recommend using an index for (xuid, realm_id, online, last_seen DESC)
        table = "realmplayersession"

    custom_id: UUID = fields.UUIDField(pk=True)
    realm_id: str = fields.CharField(50)
    xuid: str = fields.CharField(50)
    online: bool = fields.BooleanField(default=False)  # type: ignore
    last_seen: datetime = fields.DatetimeField()
    joined_at: typing.Optional[datetime] = fields.DatetimeField(null=True)

    gamertag: typing.Optional[str] = None
    device: typing.Optional[str] = None
    show_left: bool = True

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


class PremiumCode(Model):
    class Meta:
        table = "realmpremiumcode"

    id: int = fields.IntField(pk=True)
    code: str = fields.CharField(100)
    user_id: int | None = fields.BigIntField(null=True)
    uses: int = fields.IntField(default=0)
    max_uses: int = fields.IntField(default=2)
    customer_id: typing.Optional[str] = fields.CharField(50, null=True)
    expires_at: typing.Optional[datetime] = fields.DatetimeField(null=True)

    guilds: fields.ReverseRelation["GuildConfig"]
