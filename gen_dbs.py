# use this to generate db if you need to
import os

import aiohttp
import asyncpg
import orjson
import redis.asyncio as aioredis
import tomli
from tortoise import run_async
from tortoise import Tortoise

from common.models import GuildConfig
from common.realms_api import RealmsAPI


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


async def port_from_file():  # optional to use if you have a config file from way back when
    await Tortoise.init(
        db_url=os.environ["DB_URL"], modules={"models": ["common.models"]}
    )

    document_url = os.environ["CONFIG_URL"]
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


async def migrate():
    # a basic migration from byte-based sets to something more proper
    conn: asyncpg.Connection = await asyncpg.connect(os.environ.get("DB_URL"))

    async with conn.transaction():
        await conn.execute(
            "ALTER TABLE realmguildconfig RENAME prefixes TO old_prefixes"
        )
        await conn.execute(
            "ALTER TABLE realmguildconfig ADD prefixes VARCHAR(40)[] DEFAULT '{}'"
        )

        config_data = await conn.fetch("SELECT * from realmguildconfig")

        for config in config_data:
            new_prefixes = orjson.loads(config["old_prefixes"])
            await conn.execute(
                "UPDATE realmguildconfig SET prefixes = $1",
                new_prefixes,
            )

        await conn.execute("ALTER TABLE realmguildconfig DROP COLUMN old_prefixes")

    await conn.close()


async def club_to_realms():
    conn: asyncpg.Connection = await asyncpg.connect(os.environ.get("DB_URL"))

    async with conn.transaction():
        await conn.execute("ALTER TABLE realmguildconfig ADD realm_id VARCHAR(50) NULL")
    await conn.close()

    await Tortoise.init(
        db_url=os.environ["DB_URL"], modules={"models": ["common.models"]}
    )

    realms = RealmsAPI(aiohttp.ClientSession())
    redis = aioredis.from_url(os.environ.get("REDIS_URL"), decode_responses=True)

    realms_list = await realms.fetch_realms()

    club_to_realm = {
        str(realm.club_id): str(realm.id)
        for realm in realms_list.servers
        if realm.club_id is not None
    }

    configs = []

    async for guild_config in GuildConfig.all():
        if guild_config.club_id is not None:
            realm_id = club_to_realm.get(guild_config.club_id)
            if not realm_id:
                continue

            await redis.sadd(f"realm-id-{realm_id}", str(guild_config.guild_id))
            guild_config.realm_id = realm_id
            configs.append(guild_config)

    await GuildConfig.bulk_update(configs, ["realm_id"])


run_async(init())
