# use this to generate db if you need to
import os

import aiohttp
import asyncpg
import tomli
from tortoise import run_async
from tortoise import Tortoise


CONFIG_LOCATION = os.environ.get("CONFIG_LOCATION", "config.toml")
with open(CONFIG_LOCATION, "rb") as f:
    toml_dict = tomli.load(f)
    for key, value in toml_dict.items():
        os.environ[key] = str(value)


async def init():
    await Tortoise.init(
        db_url=os.environ["DB_URL"], modules={"models": ["common.models"]}
    )
    await Tortoise.generate_schemas()


run_async(init())
