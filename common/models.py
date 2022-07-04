import typing
from datetime import datetime

from tortoise import fields
from tortoise.contrib.postgres.fields import ArrayField
from tortoise.models import Model


class SetField(ArrayField, set):
    """A somewhat exploity way of using an array field to store a set."""

    def to_python_value(self, value):
        value = None if value is None else set(value)
        self.validate(value)
        return value

    def to_db_value(self, value, _):
        self.validate(value)
        value = None if value is None else list(value)
        return value


class GuildConfig(Model):
    class Meta:
        table = "realmguildconfig"

    guild_id: int = fields.BigIntField(pk=True)
    club_id: typing.Optional[str] = fields.CharField(50, null=True)
    playerlist_chan: typing.Optional[int] = fields.BigIntField(null=True)
    online_cmd: bool = fields.BooleanField(default=False)  # type: ignore
    prefixes: typing.Set[str] = SetField("VARCHAR(40)")
    realm_id: typing.Optional[str] = fields.CharField(50, null=True)
    premium_code: fields.ForeignKeyNullableRelation[
        "PremiumCode"
    ] = fields.ForeignKeyField(
        "models.PremiumCode",
        related_name="guilds",
        on_delete=fields.SET_NULL,
        null=True,
    )  # type: ignore


class RealmPlayer(Model):
    class Meta:
        table = "realmplayer"

    realm_xuid_id: str = fields.CharField(max_length=100, pk=True)
    online: bool = fields.BooleanField(default=False)  # type: ignore
    last_seen: datetime = fields.DatetimeField()


class PremiumCode(Model):
    class Meta:
        table = "realmpremiumcode"

    id: int = fields.IntField(pk=True)
    code: str = fields.CharField(100)
    user_id: int = fields.BigIntField(null=True)
    uses: int = fields.IntField(default=0)
    max_uses: int = fields.IntField(default=1)

    guilds: fields.ReverseRelation["GuildConfig"]
