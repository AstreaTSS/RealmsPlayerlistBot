import asyncio
import contextlib
import datetime
import importlib
import logging
import os
import typing
from collections import defaultdict

import aiohttp
import discord_typings
import naff
import sentry_sdk
import tomli
from tortoise import Tortoise
from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.authentication.manager import AuthenticationManager
from xbox.webapi.authentication.models import OAuth2TokenResponse

import common.help_tools as help_tools
import common.models as models
import common.utils as utils
from common.classes import SemaphoreRedis
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

naff_logger = logging.getLogger("naff")
naff_logger.setLevel(logging.INFO)
naff_logger.addHandler(handler)


def default_sentry_filter(
    event: dict[str, typing.Any], hint: dict[str, typing.Any]
) -> typing.Optional[dict[str, typing.Any]]:
    if "log_record" in hint:
        record: logging.LogRecord = hint["log_record"]
        if "naff" in record.name:
            #  There are some logging messages that are not worth sending to sentry.
            if ": 403" in record.message:
                return None
            if ": 404" in record.message:
                return None
            if record.message.startswith("Ignoring exception in "):
                return None

    if "exc_info" in hint:
        exc_type, exc_value, tb = hint["exc_info"]
        if isinstance(exc_value, KeyboardInterrupt):
            #  We don't need to report a ctrl+c
            return None
    return event


sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], before_send=default_sentry_filter)


class RealmsPlayerlistBot(utils.RealmBotBase):
    @naff.listen("startup")
    async def on_startup(self):
        self.redis = SemaphoreRedis.from_url(
            os.environ["REDIS_URL"], decode_responses=True, semaphore_value=15
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

        profile = await xbl_client.profile.get_profile_by_xuid(str(xbl_client.xuid))
        user = profile.profile_users[0]
        self.own_gamertag = next(s.value for s in user.settings if s.id == "Gamertag")

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

    @naff.listen("raw_application_command_permissions_update")
    async def i_like_my_events_very_raw(self, event: naff.events.RawGatewayEvent):
        data: discord_typings.GuildApplicationCommandPermissionData = event.data  # type: ignore

        guild_id = int(data["guild_id"])

        if not self.slash_perms_cache[guild_id]:
            await help_tools.process_bulk_slash_perms(self, guild_id)
            return

        cmds = help_tools.get_commands_for_scope_by_ids(self, guild_id)
        if cmd := cmds.get(int(data["id"])):
            self.slash_perms_cache[guild_id][
                int(data["id"])
            ] = help_tools.PermissionsResolver(
                cmd.default_member_permissions, guild_id, data["permissions"]  # type: ignore
            )

    async def on_error(self, source: str, error: Exception, *args, **kwargs) -> None:
        await utils.error_handle(self, error)

    async def stop(self) -> None:
        await bot.session.close()
        await bot.realms.close()
        return await super().stop()


intents = naff.Intents.new(
    default=False,
    guilds=True,
    messages=True,
)
mentions = naff.AllowedMentions.all()

bot = RealmsPlayerlistBot(
    sync_interactions=False,  # big bots really shouldn't have this on
    allowed_mentions=mentions,
    intents=intents,
    interaction_context=utils.RealmContext,
    autocomplete_context=utils.RealmAutocompleteContext,
    prefixed_context=utils.RealmPrefixedContext,
    auto_defer=naff.AutoDefer(enabled=True, time_until_defer=0),
    message_cache=naff.utils.TTLCache(10, 5, 5),  # we do not need messages
    logger=logger,
)
bot.init_load = True
bot.color = naff.Color(int(os.environ["BOT_COLOR"]))  # 8ac249, aka 9093705
bot.online_cache = defaultdict(set)
bot.slash_perms_cache = defaultdict(dict)
bot.mini_commands_per_scope = {}


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

    bot.realm_name_cache = TimedDict(expires=300)
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
