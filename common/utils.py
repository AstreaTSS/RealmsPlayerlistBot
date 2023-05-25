import asyncio
import collections
import datetime
import os
import traceback
import typing
import uuid
from collections import defaultdict
from pathlib import Path

import aiohttp
import interactions as ipy
import redis.asyncio as aioredis
import sentry_sdk
from interactions.ext import prefixed_commands as prefixed

from common.models import GuildConfig

TEST_MODE: bool = os.environ.get("TEST_MODE", False)  # type: ignore

DEV_GUILD_ID = int(os.environ.get("DEV_GUILD_ID", "0"))
XBOX_API_RELYING_PARTY = "http://xboxlive.com"
REALMS_API_URL = "https://pocket.realms.minecraft.net/"
MC_VERSION = "1.19.0"  # this can be a few versions behind

EXPIRE_GAMERTAGS_AT = int(datetime.timedelta(days=14).total_seconds())


async def sleep_until(dt: datetime.datetime) -> None:
    if dt.tzinfo is None:
        dt = dt.astimezone()
    now = datetime.datetime.now(datetime.UTC)
    time_to_sleep = max((dt - now).total_seconds(), 0)
    await asyncio.sleep(time_to_sleep)


async def error_handle(
    error: Exception, *, ctx: typing.Optional[ipy.BaseContext] = None
) -> None:
    if not isinstance(error, aiohttp.ServerDisconnectedError):
        if TEST_MODE:
            traceback.print_exception(error)
        else:
            with sentry_sdk.configure_scope() as scope:
                if ctx:
                    scope.set_context(
                        type(ctx).__name__,
                        {
                            "args": ctx.args,  # type: ignore
                            "kwargs": ctx.kwargs,  # type: ignore
                            "message": ctx.message,
                        },
                    )
                sentry_sdk.capture_exception(error)
    if ctx:
        if isinstance(ctx, prefixed.PrefixedContext):
            await ctx.reply(
                "An internal error has occured. The bot owner has been notified."
            )
        elif isinstance(ctx, ipy.InteractionContext):
            await ctx.send(
                content=(
                    "An internal error has occured. The bot owner has been notified."
                )
            )


async def msg_to_owner(
    bot: "RealmBotBase", content: typing.Any, split: bool = True
) -> None:
    # sends a message to the owner
    string = str(content) if split else content

    str_chunks = string_split(string) if split else content
    for chunk in str_chunks:
        await bot.bot_owner.send(f"{chunk}")


def line_split(content: str, split_by: int = 20) -> list[list[str]]:
    content_split = content.splitlines()
    return [
        content_split[x : x + split_by] for x in range(0, len(content_split), split_by)
    ]


def embed_check(embed: ipy.Embed) -> bool:
    """
    Checks if an embed is valid, as per Discord's guidelines.
    See https://discord.com/developers/docs/resources/channel#embed-limits for details.
    """
    if len(embed) > 6000:
        return False

    if embed.title and len(embed.title) > 256:
        return False
    if embed.description and len(embed.description) > 4096:
        return False
    if embed.author and embed.author.name and len(embed.author.name) > 256:
        return False
    if embed.footer and embed.footer.text and len(embed.footer.text) > 2048:
        return False
    if embed.fields:
        if len(embed.fields) > 25:
            return False
        for field in embed.fields:
            if field.name and len(field.name) > 1024:
                return False
            if field.value and len(field.value) > 2048:
                return False

    return True


def deny_mentions(user: ipy.BaseUser) -> ipy.AllowedMentions:
    # generates an AllowedMentions object that only pings the user specified
    return ipy.AllowedMentions(users=[user])


def error_format(error: Exception) -> str:
    # simple function that formats an exception
    return "".join(
        traceback.format_exception(  # type: ignore
            type(error), value=error, tb=error.__traceback__
        )
    )


def string_split(string: str) -> list[str]:
    # simple function that splits a string into 1950-character parts
    return [string[i : i + 1950] for i in range(0, len(string), 1950)]


def file_to_ext(str_path: str, base_path: str) -> str:
    # changes a file to an import-like string
    str_path = str_path.replace(base_path, "")
    str_path = str_path.replace("/", ".")
    return str_path.replace(".py", "")


def get_all_extensions(str_path: str, folder: str = "exts") -> collections.deque[str]:
    # gets all extensions in a folder
    ext_files: collections.deque[str] = collections.deque()
    loc_split = str_path.split(folder)
    base_path = loc_split[0]

    if base_path == str_path:
        base_path = base_path.replace("main.py", "")
    base_path = base_path.replace("\\", "/")

    if base_path[-1] != "/":
        base_path += "/"

    pathlist = Path(f"{base_path}/{folder}").glob("**/*.py")
    for path in pathlist:
        str_path = str(path.as_posix())
        str_path = file_to_ext(str_path, base_path)

        if str_path != "exts.db_handler":
            ext_files.append(str_path)

    return ext_files


def toggle_friendly_str(bool_to_convert: bool) -> typing.Literal["on", "off"]:
    return "on" if bool_to_convert else "off"


def yesno_friendly_str(bool_to_convert: bool) -> typing.Literal["yes", "no"]:
    return "yes" if bool_to_convert else "no"


def na_friendly_str(obj: typing.Any) -> str:
    return str(obj) if obj else "N/A"


def error_embed_generate(error_msg: str) -> ipy.Embed:
    return ipy.Embed(color=ipy.MaterialColors.RED, description=error_msg)


class CustomCheckFailure(ipy.errors.BadArgument):
    # custom classs for custom prerequisite failures outside of normal command checks
    pass


class RealmContextMixin:
    guild_config: typing.Optional[GuildConfig]

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.guild_config = None
        super().__init__(*args, **kwargs)

    @property
    def guild(self) -> ipy.Guild:
        return self.client.cache.get_guild(self.guild_id)  # type: ignore

    @property
    def bot(self) -> "RealmBotBase":
        """A reference to the bot instance."""
        return self.client  # type: ignore

    async def fetch_config(self) -> GuildConfig:
        """
        Gets the configuration for the context's guild.

        Returns:
            GuildConfig: The guild config.
        """
        if self.guild_config:
            return self.guild_config

        config = await GuildConfig.get_or_none(guild_id=self.guild.id).prefetch_related(
            "premium_code"
        )
        if not config:
            config = await GuildConfig.create(guild_id=self.guild.id)
        self.guild_config = config
        return config


class RealmInteractionContext(RealmContextMixin, ipy.InteractionContext):
    pass


class RealmContext(RealmContextMixin, ipy.SlashContext):
    pass


class RealmComponentContext(RealmContextMixin, ipy.ComponentContext):
    pass


class RealmContextMenuContext(RealmContextMixin, ipy.ContextMenuContext):
    pass


class RealmModalContext(RealmContextMixin, ipy.ModalContext):
    pass


class RealmPrefixedContext(RealmContextMixin, prefixed.PrefixedContext):
    pass


class RealmAutocompleteContext(RealmContextMixin, ipy.AutocompleteContext):
    pass


if typing.TYPE_CHECKING:
    from ordered_set import OrderedSet

    from .classes import TimedDict
    from .help_tools import MiniCommand, PermissionsResolver
    from .realms_api import RealmsAPI
    from .xbox_api import XboxAPI

    class RealmBotBase(prefixed.PrefixedInjectedClient):
        bot_owner: ipy.User
        color: ipy.Color
        init_load: bool
        fully_ready: asyncio.Event
        pl_sem: asyncio.Semaphore

        session: aiohttp.ClientSession
        openxbl_session: aiohttp.ClientSession
        xbox: XboxAPI
        realms: RealmsAPI
        redis: aioredis.Redis
        own_gamertag: str
        background_tasks: set[asyncio.Task]

        online_cache: defaultdict[int, set[str]]
        realm_name_cache: TimedDict[typing.Optional[str], str]
        slash_perms_cache: defaultdict[int, dict[int, PermissionsResolver]]
        mini_commands_per_scope: dict[int, dict[str, MiniCommand]]
        live_playerlist_store: defaultdict[str, set[int]]
        uuid_cache: defaultdict[str, uuid.UUID]
        offline_realms: OrderedSet[int]
        dropped_offline_realms: set[int]

        def mention_cmd(self, name: str, scope: int = 0) -> str:
            ...

        def create_task(
            self, coro: typing.Coroutine[typing.Any, typing.Any, ipy.const.T]
        ) -> asyncio.Task[ipy.const.T]:
            ...

else:

    class RealmBotBase(ipy.Client):
        pass


async def _global_checks(ctx: ipy.BaseContext) -> bool:
    # sourcery skip: assign-if-exp, boolean-if-exp-identity, hoist-statement-from-if, reintroduce-else, swap-if-expression
    if not ctx.bot.fully_ready.is_set():  # type: ignore
        return False

    if not ctx.guild:
        return False

    if ctx.author.id in ctx.bot.owner_ids:
        return True

    return True


class Extension(ipy.Extension):
    def __new__(
        cls, bot: ipy.Client, *args: typing.Any, **kwargs: typing.Any
    ) -> ipy.Extension:
        new_cls = super().__new__(cls, bot, *args, **kwargs)
        new_cls.add_ext_check(_global_checks)  # type: ignore
        return new_cls


class GuildMessageable(ipy.GuildChannel, ipy.MessageableMixin):
    pass
