"""
Copyright 2020-2023 AstreaTSS.
This file is part of the Realms Playerlist Bot.

The Realms Playerlist Bot is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

The Realms Playerlist Bot is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with the Realms
Playerlist Bot. If not, see <https://www.gnu.org/licenses/>.
"""

import asyncio
import collections
import datetime
import logging
import os
import traceback
import typing
from collections import defaultdict
from pathlib import Path

import aiohttp
import interactions as ipy
import orjson
import redis.asyncio as aioredis
import sentry_sdk
from interactions.ext import prefixed_commands as prefixed

from common.models import GuildConfig

SENTRY_ENABLED = bool(os.environ.get("SENTRY_DSN", False))  # type: ignore

DEV_GUILD_ID = int(os.environ.get("DEV_GUILD_ID", "0"))

EXPIRE_GAMERTAGS_AT = int(datetime.timedelta(days=7).total_seconds())

logger = logging.getLogger("realms_bot")

_DEBUG: dict[str, bool] = orjson.loads(os.environ.get("DEBUG", "{}"))
_debug_defaults = {
    "HANDLE_MISSING_REALMS": True,
    "PROCESS_REALMS": True,
    "AUTORUNNER": True,
    "ETC_EVENTS": True,
    "PRINT_TRACKBACK_FOR_ERRORS": False,
    "EVENTUALLY_INVALIDATE": True,
}

REOCCURING_LB_FREQUENCY: dict[int, str] = {
    1: "Every Sunday at 12:00 AM (00:00) UTC",
    2: "Every other Sunday at 12:00 AM (00:00) UTC",
    3: "The first Sunday of every month at 12:00 AM (00:00) UTC",
}
REOCCURING_LB_PERIODS: dict[int, str] = {
    1: "24 hours",
    2: "1 week",
    3: "2 weeks",
    4: "30 days",
}


def FEATURE(feature: str) -> bool:  # noqa: N802
    return _DEBUG.get(feature, _debug_defaults[feature])


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
        if FEATURE("PRINT_TRACKBACK_FOR_ERRORS") or not SENTRY_ENABLED:
            traceback.print_exception(error)
            logger.error("An error occured.", exc_info=error)
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
                ),
                ephemeral=ctx.ephemeral,
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
    # splits strings into lists of strings, each with a max length of split_by
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


_bot_color = ipy.Color(int(os.environ["BOT_COLOR"]))


def make_embed(description: str, *, title: str | None = None) -> ipy.Embed:
    return ipy.Embed(
        title=title,
        description=description,
        color=_bot_color,
        timestamp=ipy.Timestamp.utcnow(),
    )


def error_embed_generate(error_msg: str) -> ipy.Embed:
    return ipy.Embed(
        title="Error",
        description=error_msg,
        color=ipy.MaterialColors.RED,
        timestamp=ipy.Timestamp.utcnow(),
    )


def partial_channel(
    bot: "RealmBotBase", channel_id: ipy.Snowflake_Type
) -> ipy.GuildText:
    return ipy.GuildText(client=bot, id=ipy.to_snowflake(channel_id), type=ipy.ChannelType.GUILD_TEXT)  # type: ignore


async def config_info_generate(
    ctx: "RealmContext | RealmPrefixedContext",
    config: GuildConfig,
    realm_name: str,
    *,
    diagnostic_info: bool = False,
) -> ipy.Embed:
    embed = ipy.Embed(
        color=ctx.bot.color, title="Server Config", timestamp=ipy.Timestamp.now()
    )

    playerlist_channel = (
        f"<#{config.playerlist_chan}>" if config.playerlist_chan else "N/A"
    )
    autorunner = toggle_friendly_str(bool(config.realm_id and config.playerlist_chan))
    offline_realm_ping = (
        f"<@&{config.realm_offline_role}>" if config.realm_offline_role else "N/A"
    )
    player_watchlist_ping = (
        f"<@&{config.player_watchlist_role}>" if config.player_watchlist_role else "N/A"
    )

    notification_channels = ""
    if config.notification_channels:
        notification_channels = "__Notification Channels__:\n"
    if player_watchlist := config.notification_channels.get("player_watchlist"):
        notification_channels += f"Player Watchlist Channel: <#{player_watchlist}>\n"
    if realm_offline := config.notification_channels.get("realm_offline"):
        notification_channels += f"Realm Offline Channel: <#{realm_offline}>\n"
    if reoccuring_leaderboard := config.notification_channels.get(
        "reoccuring_leaderboard"
    ):
        notification_channels += (
            f"Reoccuring Leaderboard Channel: <#{reoccuring_leaderboard}>\n"
        )

    notification_channels = notification_channels.strip()

    embed.add_field(
        "Basic Information",
        f"Realm Name: {realm_name}\n\nAutorunner Enabled: {autorunner}\nAutorun"
        f" Playerlist Channel: {playerlist_channel}\nWarning Notifications:"
        f" {toggle_friendly_str(config.warning_notifications)}\n\nRealm Offline Role:"
        f" {offline_realm_ping}\nPlayer Watchlist Role:"
        f" {player_watchlist_ping}\nPeople on Watchlist: See"
        f" {ctx.bot.mention_cmd('watchlist list')}\n\n{notification_channels}".strip(),
        inline=True,
    )

    if config.premium_code:
        live_online_msg = "N/A"
        if config.live_online_channel:
            live_online_split = config.live_online_channel.split("|")
            live_online_msg = f"https://discord.com/channels/{ctx.guild_id}/{live_online_split[0]}/{live_online_split[1]}"

        premium_linked_to = (
            f"<@{config.premium_code.user_id}>"
            if config.premium_code and config.premium_code.user_id
            else "N/A"
        )

        reoccuring_lb = (
            f"{REOCCURING_LB_PERIODS[config.reoccuring_leaderboard % 10]} every"
            f" {REOCCURING_LB_FREQUENCY[config.reoccuring_leaderboard // 10]}"
            if config.reoccuring_leaderboard
            else "N/A"
        )

        embed.add_field(
            "Premium Information",
            f"Premium Active: {yesno_friendly_str(config.valid_premium)}\nLinked To:"
            f" {premium_linked_to}\nLive Playerlist:"
            f" {toggle_friendly_str(config.live_playerlist)}\nLive Online Message:"
            f" {live_online_msg}\nDisplay Device Information:"
            f" {toggle_friendly_str(config.fetch_devices)}\nReoccuring Leaderboard:"
            f" {reoccuring_lb}",
            inline=True,
        )
    else:
        embed.fields[0].value += "\nPremium Active: no"

    if diagnostic_info:
        premium_code_id = str(config.premium_code.id) if config.premium_code else "N/A"
        dev_info_str = (
            f"Server ID: {config.guild_id}\nRealm ID:"
            f" {na_friendly_str(config.realm_id)}\nClub ID:"
            f" {na_friendly_str(config.club_id)}\nPlayerlist Channel ID:"
            f" {na_friendly_str(config.playerlist_chan)}\nRealm Offline Role"
            f" ID:{na_friendly_str(config.realm_offline_role)}\nLinked Premium ID:"
            f" {premium_code_id}\nPlayer Watchlist XUIDs:"
            f" {na_friendly_str(config.player_watchlist)}\nNotification Channels Dict:"
            f" {na_friendly_str(config.notification_channels)}\nReoccuring Leaderboard"
            f" Value: {na_friendly_str(config.reoccuring_leaderboard)}\n"
        )
        if config.premium_code:
            expires_at = (
                f"<t:{int(config.premium_code.expires_at.timestamp())}:f>"
                if config.premium_code.expires_at
                else "N/A"
            )
            dev_info_str += (
                "\nUses:"
                f" {config.premium_code.uses} used/{config.premium_code.max_uses}\nExpires"
                f" At: {expires_at}\nLive Online:"
                f" {na_friendly_str(config.live_online_channel)}"
            )

        embed.add_field(
            "Diagnostic Information",
            dev_info_str,
            inline=False,
        )
        shard_id = ctx.bot.get_shard_id(config.guild_id)
        embed.set_footer(f"Shard ID: {shard_id}")

    return embed


class CustomCheckFailure(ipy.errors.BadArgument):
    # custom classs for custom prerequisite failures outside of normal command checks
    pass


class RealmContextMixin:
    guild_config: typing.Optional[GuildConfig]
    guild_id: ipy.Snowflake

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.guild_config = None
        super().__init__(*args, **kwargs)

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
        if not self.guild_id:
            raise ValueError("No guild ID set.")

        if self.guild_config:
            return self.guild_config

        config = await GuildConfig.get_or_none(
            self.guild_id
        ) or await GuildConfig.prisma().create(data={"guild_id": self.guild_id})

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
    @property
    def channel(self) -> ipy.GuildText:
        """The channel this context was invoked in."""
        return partial_channel(self.bot, self.channel_id)


class RealmAutocompleteContext(RealmContextMixin, ipy.AutocompleteContext):
    pass


if typing.TYPE_CHECKING:
    import elytra
    from aiohttp_retry import RetryClient
    from cachetools import TTLCache
    from prisma import Prisma

    from .classes import OrderedSet
    from .help_tools import MiniCommand, PermissionsResolver
    from .splash_texts import SplashTexts

    class RealmBotBase(ipy.AutoShardedClient):
        prefixed: prefixed.PrefixedManager

        unavailable_guilds: set[int]
        bot_owner: ipy.User
        color: ipy.Color
        init_load: bool
        fully_ready: asyncio.Event
        pl_sem: asyncio.Semaphore

        db: Prisma
        session: aiohttp.ClientSession
        openxbl_session: RetryClient
        xbox: elytra.XboxAPI
        realms: elytra.BedrockRealmsAPI
        redis: aioredis.Redis
        own_gamertag: str
        background_tasks: set[asyncio.Task]
        splash_texts: SplashTexts

        online_cache: defaultdict[int, set[str]]
        realm_name_cache: TTLCache[typing.Optional[str], str]
        slash_perms_cache: defaultdict[int, dict[int, PermissionsResolver]]
        mini_commands_per_scope: dict[int, dict[str, MiniCommand]]
        live_playerlist_store: defaultdict[str, set[int]]
        player_watchlist_store: defaultdict[str, set[int]]
        uuid_cache: defaultdict[str, str]
        offline_realms: OrderedSet[int]
        dropped_offline_realms: set[int]
        fetch_devices_for: set[str]
        blacklist: set[int]

        @property
        def guild_count(self) -> int: ...

        def mention_cmd(self, name: str, scope: int = 0) -> str: ...

        def create_task(
            self, coro: typing.Coroutine[typing.Any, typing.Any, ipy.const.T]
        ) -> asyncio.Task[ipy.const.T]: ...

else:

    class RealmBotBase(ipy.AutoShardedClient):
        pass


async def _global_checks(ctx: RealmContext) -> bool:
    if ctx.author_id in ctx.bot.owner_ids:
        return True

    if int(ctx.author_id) in ctx.bot.blacklist or (
        ctx.guild_id and int(ctx.guild_id) in ctx.bot.blacklist
    ):
        return False

    return bool(ctx.bot.fully_ready.is_set())


class Extension(ipy.Extension):
    def __new__(
        cls, bot: ipy.Client, *args: typing.Any, **kwargs: typing.Any
    ) -> ipy.Extension:
        new_cls = super().__new__(cls, bot, *args, **kwargs)
        new_cls.add_ext_check(_global_checks)  # type: ignore
        return new_cls
