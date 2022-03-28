import typing

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
