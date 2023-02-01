# use this to generate db if you need to
from tortoise import Tortoise, run_async
from tortoise.connection import connections
from tortoise.utils import get_schema_sql

import db_settings
import rpl_config

rpl_config.load()


async def init() -> None:
    await Tortoise.init(db_settings.TORTOISE_ORM)

    await Tortoise.generate_schemas()


async def see_sql() -> None:
    await Tortoise.init(db_settings.TORTOISE_ORM)

    for connection in connections.all():
        print(get_schema_sql(connection, safe=False))  # noqa: T201


run_async(init())
