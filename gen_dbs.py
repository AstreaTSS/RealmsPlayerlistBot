# use this to generate db if you need to
import os
import tomllib

from tortoise import run_async
from tortoise import Tortoise
from tortoise.connection import connections
from tortoise.utils import get_schema_sql

CONFIG_LOCATION = os.environ.get("CONFIG_LOCATION", "config.toml")
with open(CONFIG_LOCATION, "rb") as f:
    toml_dict = tomllib.load(f)
    for key, value in toml_dict.items():
        os.environ[key] = str(value)


async def init():
    await Tortoise.init(
        db_url=os.environ["DB_URL"], modules={"models": ["common.models"]}
    )

    await Tortoise.generate_schemas()


async def see_sql():
    await Tortoise.init(
        db_url=os.environ["DB_URL"], modules={"models": ["common.models"]}
    )

    for connection in connections.all():
        print(get_schema_sql(connection, safe=False))


run_async(init())
