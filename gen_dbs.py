# use this to generate db if you need to
import os

import aiohttp
from dotenv import load_dotenv
from tortoise import run_async
from tortoise import Tortoise

from common.models import GuildConfig

load_dotenv()


async def init():
    await Tortoise.init(
        db_url=os.environ.get("DB_URL"), modules={"models": ["common.models"]}
    )
    await Tortoise.generate_schemas()


async def port_from_file():  # optional to use if you have a config file from way back when
    await Tortoise.init(
        db_url=os.environ.get("DB_URL"), modules={"models": ["common.models"]}
    )

    document_url = os.environ.get("CONFIG_URL")
    headers = {"Cache-Control": "no-cache", "Pragma": "no-cache"}

    async with aiohttp.ClientSession() as session:
        async with session.get(document_url, headers=headers) as resp:
            old_config: dict = await resp.json(content_type="text/plain")

    for guild_id, config_json in old_config.items():
        await GuildConfig.create(
            guild_id=int(guild_id),
            playerlist_chan=config_json["playerlist_chan"],
            club_id=config_json["club_id"]
            if config_json["club_id"] != "None"
            else None,
            online_cmd=config_json["online_cmd"],
            prefixes={"!?"},
        )


run_async(init())
