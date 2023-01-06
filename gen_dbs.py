# use this to generate db if you need to
import os
import tomllib
import typing
import uuid
from datetime import datetime

from tortoise import Tortoise, fields, run_async
from tortoise.connection import connections
from tortoise.models import Model
from tortoise.utils import get_schema_sql

import common.models as models

CONFIG_LOCATION = os.environ.get("CONFIG_LOCATION", "config.toml")
with open(CONFIG_LOCATION, "rb") as f:
    toml_dict = tomllib.load(f)
    for key, value in toml_dict.items():
        os.environ[key] = str(value)


class RealmPlayer(Model):
    class Meta:
        table = "realmplayer"

    realm_xuid_id: str = fields.CharField(max_length=100, pk=True)
    online: bool = fields.BooleanField(default=False)  # type: ignore
    last_seen: datetime = fields.DatetimeField()
    last_joined: typing.Optional[datetime] = fields.DatetimeField(null=True)


async def init() -> None:
    await Tortoise.init(
        db_url=os.environ["DB_URL"], modules={"models": ["common.models"]}
    )

    await Tortoise.generate_schemas()


async def migrate_realmplayer() -> None:
    await Tortoise.init(
        db_url=os.environ["DB_URL"], modules={"models": ["common.models", "__main__"]}
    )
    await Tortoise.generate_schemas()

    player_sessions: list[models.PlayerSession] = []

    async for realm_player in RealmPlayer.all():
        realm_id, xuid = realm_player.realm_xuid_id.split("-")

        player_sessions.append(
            models.PlayerSession(
                custom_id=uuid.uuid4(),
                realm_id=realm_id,
                xuid=xuid,
                online=realm_player.online,
                last_seen=realm_player.last_seen,
                joined_at=realm_player.last_joined,
            )
        )

    await models.PlayerSession.bulk_create(player_sessions)


async def see_sql() -> None:
    await Tortoise.init(
        db_url=os.environ["DB_URL"], modules={"models": ["common.models"]}
    )

    for connection in connections.all():
        print(get_schema_sql(connection, safe=False))  # noqa: T201


run_async(init())
