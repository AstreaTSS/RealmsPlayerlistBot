import asyncio
import datetime
import logging
import os

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv
from websockets import ConnectionClosedOK
from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.authentication.manager import AuthenticationManager
from xbox.webapi.authentication.models import OAuth2TokenResponse

import common.utils as utils
import keep_alive
from common.help_cmd import PaginatedHelpCommand
from common.profile_custom import ProfileProvider


# load_dotenv()

logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(
    filename=os.environ.get("LOG_FILE_PATH"), encoding="utf-8", mode="a"
)
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)


async def realms_plus_prefixes(bot: commands.Bot, msg: discord.Message):
    mention_prefixes = {f"{bot.user.mention} ", f"<@!{bot.user.id}> "}
    custom_prefixes = {"!?"}
    return mention_prefixes.union(custom_prefixes)


def global_checks(ctx: commands.Context):
    if not ctx.bot.is_ready():
        return False

    if ctx.bot.init_load:
        return False

    if not ctx.guild:
        return False

    if ctx.author.id == ctx.bot.owner.id:
        return True

    return not (
        ctx.guild.id == 775912554928144384
        and ctx.command.qualified_name not in ("help", "ping")
    )


async def on_init_load():
    await bot.wait_until_ready()

    application = await bot.application_info()
    bot.owner = application.owner

    bot.session = aiohttp.ClientSession()
    auth_mgr = AuthenticationManager(
        bot.session, os.environ.get("CLIENT_ID"), os.environ.get("CLIENT_SECRET"), ""
    )
    auth_mgr.oauth = OAuth2TokenResponse.parse_raw(os.environ.get("XAPI_TOKENS"))
    await auth_mgr.refresh_tokens()
    xbl_client = XboxLiveClient(auth_mgr)
    bot.profile = ProfileProvider(xbl_client)

    bot.load_extension("jishaku")
    bot.load_extension("cogs.config_fetch")
    while bot.config == {}:
        await asyncio.sleep(0.1)

    cogs_list = utils.get_all_extensions(os.environ.get("DIRECTORY_OF_FILE"))

    for cog in cogs_list:
        if cog != "cogs.config_fetch":
            try:
                bot.load_extension(cog)
            except commands.NoEntryPointError:
                pass


class RealmsPlusBot(commands.Bot):
    def __init__(
        self,
        command_prefix,
        help_command=PaginatedHelpCommand(),
        description=None,
        **options,
    ):
        super().__init__(
            command_prefix,
            help_command=help_command,
            description=description,
            **options,
        )
        self._checks.append(global_checks)

    async def on_ready(self):
        utcnow = datetime.datetime.now(tz=datetime.timezone.utc)
        time_format = f"<t:{int(utcnow.timestamp())}:f>"

        connect_msg = (
            f"Logged in at {time_format}!"
            if self.init_load == True
            else f"Reconnected at {time_format}!"
        )

        while (
            not hasattr(self, "owner")
            or not hasattr(self, "config")
            or self.config == {}
        ):
            await asyncio.sleep(0.1)

        await self.owner.send(connect_msg)

        self.init_load = False

        activity = discord.Activity(
            name="over some Realms Plus realms", type=discord.ActivityType.watching
        )

        try:
            await self.change_presence(activity=activity)
        except ConnectionClosedOK:
            await utils.msg_to_owner(self, "Reconnecting...")

    async def on_resumed(self):
        activity = discord.Activity(
            name="over some Realms Plus realms", type=discord.ActivityType.watching
        )
        await self.change_presence(activity=activity)

    async def on_error(self, event, *args, **kwargs):
        try:
            raise
        except BaseException as e:
            await utils.error_handle(self, e)

    async def get_context(self, message, *, cls=commands.Context):
        """A simple extension of get_content. If it doesn't manage to get a command, it changes the string used
        to get the command from - to _ and retries. Convenient for the end user."""

        ctx = await super().get_context(message, cls=cls)
        if ctx.command is None and ctx.invoked_with:
            ctx.command = self.all_commands.get(ctx.invoked_with.replace("-", "_"))

        return ctx

    async def close(self) -> None:
        await bot.session.close()
        return await super().close()


intents = discord.Intents.all()
mentions = discord.AllowedMentions.all()

bot = RealmsPlusBot(
    command_prefix=realms_plus_prefixes, allowed_mentions=mentions, intents=intents,
)

bot.init_load = True
bot.color = discord.Color(int(os.environ.get("BOT_COLOR")))  # 8ac249, aka 9093705
bot.config = {}
bot.gamertags = {}
bot.pastebins = {}

bot.loop.create_task(on_init_load())
keep_alive.keep_alive()
bot.run(os.environ.get("MAIN_TOKEN"))
