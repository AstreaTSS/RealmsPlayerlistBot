#!/usr/bin/env python3.8
import asyncio
import collections
import datetime
import logging
import os
import traceback
import typing
from pathlib import Path

import aiohttp
import aioredis
import naff

from .models import GuildConfig


DEV_GUILD_ID = int(os.environ.get("DEV_GUILD_ID", "0"))
REALMS_API_URL = "https://pocket.realms.minecraft.net/"
MC_VERSION = "1.19.0"  # this can be a few versions behind


async def sleep_until(dt: datetime.datetime):
    if dt.tzinfo is None:
        dt = dt.astimezone()
    now = datetime.datetime.now(datetime.timezone.utc)
    time_to_sleep = max((dt - now).total_seconds(), 0)
    await asyncio.sleep(time_to_sleep)


async def error_handle(bot: "RealmBotBase", error: Exception, ctx: naff.Context = None):
    # handles errors and sends them to owner
    if isinstance(error, aiohttp.ServerDisconnectedError):
        to_send = "Disconnected from server!"
        split = True
    else:
        error_str = error_format(error)
        logging.getLogger(naff.const.logger_name).error(error_str)

        chunks = line_split(error_str)
        for i in range(len(chunks)):
            chunks[i][0] = f"```py\n{chunks[i][0]}"
            chunks[i][len(chunks[i]) - 1] += "\n```"

        final_chunks = ["\n".join(chunk) for chunk in chunks]
        if ctx and hasattr(ctx, "message") and hasattr(ctx.message, "jump_url"):
            final_chunks.insert(0, f"Error on: {ctx.message.jump_url}")

        to_send = final_chunks
        split = False

    await msg_to_owner(bot, to_send, split)

    if ctx:
        if isinstance(ctx, naff.PrefixedContext):
            await ctx.reply(
                "An internal error has occured. The bot owner has been notified."
            )
        elif isinstance(ctx, naff.InteractionContext):
            await ctx.send(
                content=(
                    "An internal error has occured. The bot owner has been notified."
                )
            )


async def msg_to_owner(bot: "RealmBotBase", content, split=True):
    # sends a message to the owner
    string = str(content)

    str_chunks = string_split(string) if split else content
    for chunk in str_chunks:
        await bot.owner.send(f"{chunk}")


def line_split(content: str, split_by=20):
    content_split = content.splitlines()
    return [
        content_split[x : x + split_by] for x in range(0, len(content_split), split_by)
    ]


def embed_check(embed: naff.Embed) -> bool:
    """Checks if an embed is valid, as per Discord's guidelines.
    See https://discord.com/developers/docs/resources/channel#embed-limits for details."""
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


def deny_mentions(user):
    # generates an AllowedMentions object that only pings the user specified
    return naff.AllowedMentions(users=[user])


def error_format(error: Exception):
    # simple function that formats an exception
    return "".join(
        traceback.format_exception(  # type: ignore
            type(error), value=error, tb=error.__traceback__
        )
    )


def string_split(string):
    # simple function that splits a string into 1950-character parts
    return [string[i : i + 1950] for i in range(0, len(string), 1950)]


def file_to_ext(str_path, base_path):
    # changes a file to an import-like string
    str_path = str_path.replace(base_path, "")
    str_path = str_path.replace("/", ".")
    return str_path.replace(".py", "")


def get_all_extensions(str_path, folder="exts"):
    # gets all extensions in a folder
    ext_files = collections.deque()
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


def toggle_friendly_str(bool_to_convert):
    return "on" if bool_to_convert == True else "off"


def yesno_friendly_str(bool_to_convert):
    return "yes" if bool_to_convert == True else "no"


def error_embed_generate(error_msg):
    return naff.Embed(color=naff.MaterialColors.RED, description=error_msg)


class CustomCheckFailure(naff.errors.BadArgument):
    # custom classs for custom prerequisite failures outside of normal command checks
    pass


@naff.utils.define
class RealmContext(naff.InteractionContext):
    guild_config: typing.Optional[GuildConfig] = naff.utils.field(default=None)

    @property
    def guild(self) -> naff.Guild:
        return self._client.cache.get_guild(self.guild_id)  # type: ignore

    @property
    def bot(self) -> "RealmBotBase":
        """A reference to the bot instance."""
        return self._client  # type: ignore

    async def fetch_config(self) -> GuildConfig:
        """
        Gets the configuration for the context's guild.

        Returns:
            GuildConfig: The guild config.
        """
        if self.guild_config:
            return self.guild_config

        config = await GuildConfig.get(guild_id=self.guild.id)
        self.guild_config = config
        return config


@naff.utils.define
class RealmPrefixedContext(naff.PrefixedContext):
    guild_config: typing.Optional[GuildConfig] = naff.utils.field(default=None)

    @property
    def guild(self) -> naff.Guild:
        return self._client.cache.get_guild(self.guild_id)  # type: ignore

    @property
    def bot(self) -> "RealmBotBase":
        """A reference to the bot instance."""
        return self._client  # type: ignore

    async def fetch_config(self) -> GuildConfig:
        """
        Gets the configuration for the context's guild.

        Returns:
            GuildConfig: The guild config.
        """
        if self.guild_config:
            return self.guild_config

        config = await GuildConfig.get(guild_id=self.guild.id)
        self.guild_config = config
        return config


if typing.TYPE_CHECKING:
    from .custom_providers import ProfileProvider, ClubProvider
    from .realms_api import RealmsAPI

    class RealmBotBase(naff.Client):
        init_load: bool
        color: naff.Color
        session: aiohttp.ClientSession
        openxbl_session: aiohttp.ClientSession
        realms: RealmsAPI
        profile: ProfileProvider
        club: ClubProvider
        owner: naff.User
        redis: aioredis.Redis
        fully_ready: asyncio.Event

else:

    class RealmBotBase(naff.Client):
        pass


async def _global_checks(ctx: naff.Context):
    if not ctx.bot.is_ready:
        return False

    if ctx.bot.init_load:  # type: ignore
        return False

    if not ctx.guild:
        return False

    if ctx.author.id == ctx.bot.owner.id:
        return True

    return True


class Extension(naff.Extension):
    def __new__(cls, bot: naff.Client, *args, **kwargs):
        new_cls = super().__new__(cls, bot, *args, **kwargs)
        new_cls.add_ext_check(_global_checks)  # type: ignore
        return new_cls
