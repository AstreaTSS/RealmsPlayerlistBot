import typing
from datetime import datetime
from uuid import UUID

from tortoise import fields
from tortoise.models import Model


class GuildConfig(Model):
    class Meta:
        table = "realmguildconfig"

    guild_id: int = fields.BigIntField(pk=True)
    club_id: typing.Optional[str] = fields.CharField(50, null=True)
    playerlist_chan: typing.Optional[int] = fields.BigIntField(null=True)
    realm_id: typing.Optional[str] = fields.CharField(50, null=True)
    live_playerlist: bool = fields.BooleanField(default=False)  # type: ignore
    realm_offline_role: typing.Optional[int] = fields.BigIntField(null=True)
    premium_code: fields.ForeignKeyNullableRelation[
        "PremiumCode"
    ] = fields.ForeignKeyField(
        "models.PremiumCode",
        related_name="guilds",
        on_delete=fields.SET_NULL,
        null=True,
    )  # type: ignore


class PlayerSession(Model):
    class Meta:
        table = "realmplayersession"
        indexes = ("realm_id", "xuid", "last_seen", "joined_at")

    custom_id: UUID = fields.UUIDField(pk=True)
    realm_id: str = fields.CharField(50)
    xuid: str = fields.CharField(50)
    online: bool = fields.BooleanField(default=False)  # type: ignore
    last_seen: datetime = fields.DatetimeField()
    joined_at: typing.Optional[datetime] = fields.DatetimeField(null=True)

    @property
    def realm_xuid_id(self) -> str:
        return f"{self.realm_id}-{self.xuid}"


class PremiumCode(Model):
    class Meta:
        table = "realmpremiumcode"

    id: int = fields.IntField(pk=True)
    code: str = fields.CharField(100)
    user_id: int = fields.BigIntField(null=True)
    uses: int = fields.IntField(default=0)
    max_uses: int = fields.IntField(default=1)

    guilds: fields.ReverseRelation["GuildConfig"]
