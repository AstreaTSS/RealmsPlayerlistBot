import json
import typing

from tortoise import fields
from tortoise.models import Model


class SetField(fields.BinaryField, set):
    """A very exploity way of using a binary field to store a set."""

    def json_dumps(self, value):
        return bytes(json.dumps(value), "utf-8")

    def json_loads(self, value: str):
        return json.loads(value)

    def to_python_value(self, value):
        if value is not None and isinstance(value, self.field_type):  # if its bytes
            value = set(self.json_loads(value))  # loading it would return a list, so...
        return value or set()  # empty bytes value go brr

    def to_db_value(self, value, instance):
        if value is not None and not isinstance(
            value, self.field_type
        ):  # if its not bytes
            if isinstance(value, set):  # this is a dumb fix
                value = self.json_dumps(list(value))  # returns a bytes value
            else:
                value = self.json_dumps(value)
            # the reason why i chose using BinaryField over JSONField
            # was because orjson returns bytes, and orjson's fast
        return value


class GuildConfig(Model):
    class Meta:
        table = "realmguildconfig"

    guild_id: int = fields.BigIntField(pk=True)
    club_id: str = fields.CharField(50, null=True)
    playerlist_chan: int = fields.BigIntField(null=True)
    online_cmd: bool = fields.BooleanField(default=False)  # type: ignore
    prefixes: typing.Set[str] = SetField()
