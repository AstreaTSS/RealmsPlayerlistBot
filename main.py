import asyncio
import contextlib
import datetime
import importlib
import logging
import os
from collections import defaultdict

import aiohttp
import naff
import redis.asyncio as aioredis
import tomli
from tortoise import Tortoise
from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.authentication.manager import AuthenticationManager
from xbox.webapi.authentication.models import OAuth2TokenResponse

import common.models as models
import common.utils as utils
from common.classes import TimedDict
from common.custom_providers import ClubProvider
from common.custom_providers import ProfileProvider
from common.realms_api import RealmsAPI

# load the config file into environment variables
# this allows an easy way to access these variables from any file
# we allow the user to set a configuration location via an already-set
# env var if they wish, but it'll default to config.toml in the running
# directory
CONFIG_LOCATION = os.environ.get("CONFIG_LOCATION", "config.toml")
with open(CONFIG_LOCATION, "rb") as f:
    toml_dict = tomli.load(f)
    for key, value in toml_dict.items():
        os.environ[key] = str(value)

importlib.reload(utils)  # refresh the dev guild id

try:
    import rook

    if os.environ.get("ROOK_TOKEN"):
        rook.start(
            token=os.environ["ROOK_TOKEN"], labels={"env": os.environ["ROOK_ENV"]}
        )
except ImportError:
    pass

logger = logging.getLogger("realms_bot")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(
    filename=os.environ["LOG_FILE_PATH"], encoding="utf-8", mode="a"
)
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)


class RealmsPlayerlistBot(utils.RealmBotBase):
    @naff.listen("startup")
    async def on_startup(self):
        self.redis = aioredis.from_url(
            os.environ.get("REDIS_URL"), decode_responses=True
        )

        self.session = aiohttp.ClientSession()
        auth_mgr = AuthenticationManager(
            self.session,
            os.environ["XBOX_CLIENT_ID"],
            os.environ["XBOX_CLIENT_SECRET"],
            "",
        )
        auth_mgr.oauth = OAuth2TokenResponse.parse_file(
            os.environ["XAPI_TOKENS_LOCATION"]
        )
        await auth_mgr.refresh_tokens()
        xbl_client = XboxLiveClient(auth_mgr)
        self.profile = ProfileProvider(xbl_client)
        self.club = ClubProvider(xbl_client)

        self.realms = RealmsAPI(aiohttp.ClientSession())

        headers = {
            "X-Authorization": os.environ["OPENXBL_KEY"],
            "Accept": "application/json",
            "Accept-Language": "en-US",
        }
        self.openxbl_session = aiohttp.ClientSession(headers=headers)

        self.fully_ready.set()

    @naff.listen("ready")
    async def on_ready(self):
        utcnow = naff.Timestamp.utcnow()
        time_format = f"<t:{int(utcnow.timestamp())}:f>"

        connect_msg = (
            f"Logged in at {time_format}!"
            if self.init_load == True
            else f"Reconnected at {time_format}!"
        )

        await self.owner.send(connect_msg)

        self.init_load = False

        activity = naff.Activity.create(
            name="over some Realms", type=naff.ActivityType.WATCHING
        )

        await self.change_presence(activity=activity)

    @naff.listen("disconnect")
    async def on_disconnect(self):
        # basically, this needs to be done as otherwise, when the bot reconnects,
        # redis may complain that a connection was closed by a peer
        # this isnt a great solution, but it should work
        with contextlib.suppress(Exception):
            await self.redis.connection_pool.disconnect(inuse_connections=True)

    @naff.listen("resume")
    async def on_resumed(self):
        activity = naff.Activity.create(
            name="over some Realms", type=naff.ActivityType.WATCHING
        )
        await self.change_presence(activity=activity)

    async def on_error(self, source: str, error: Exception, *args, **kwargs) -> None:
        await utils.error_handle(self, error)

    async def stop(self) -> None:
        await bot.session.close()
        await bot.realms.close()
        return await super().stop()


intents = naff.Intents.new(
    guilds=True,
    messages=True,
)
mentions = naff.AllowedMentions.all()

bot = RealmsPlayerlistBot(
    allowed_mentions=mentions,
    intents=intents,
    interaction_context=utils.RealmContext,
    prefixed_context=utils.RealmPrefixedContext,
    auto_defer=naff.AutoDefer(enabled=True, time_until_defer=0),
    message_cache=naff.utils.TTLCache(10, 5, 5),  # we do not need messages
    logger=logger,
)
bot.init_load = True
bot.color = naff.Color(int(os.environ["BOT_COLOR"]))  # 8ac249, aka 9093705
bot.online_cache = defaultdict(set)
bot.realm_name_cache = TimedDict(expires=300)


async def start():
    await Tortoise.init(
        db_url=os.environ.get("DB_URL"), modules={"models": ["common.models"]}
    )

    # mark players as offline if they were online more than 5 minutes ago
    five_minutes_ago = naff.Timestamp.utcnow() - datetime.timedelta(minutes=5)
    await models.RealmPlayer.filter(online=True, last_seen__lt=five_minutes_ago).update(
        online=False
    )

    # add all online players to the online cache
    async for player in models.RealmPlayer.filter(online=True):
        realm_id, xuid = player.realm_xuid_id.split("-")
        bot.online_cache[int(realm_id)].add(xuid)

    bot.fully_ready = asyncio.Event()

    ext_list = utils.get_all_extensions(os.environ.get("DIRECTORY_OF_BOT"))
    for ext in ext_list:
        try:
            bot.load_extension(ext)
        except naff.errors.ExtensionLoadException:
            raise

    await bot.astart(os.environ.get("MAIN_TOKEN"))


with contextlib.suppress(ImportError):
    import uvloop  # type: ignore

    uvloop.install()

asyncio.run(start())
