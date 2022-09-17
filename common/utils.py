import asyncio
import collections
import datetime
import os
import traceback
import typing
from collections import defaultdict
from pathlib import Path

import aiohttp
import naff
import redis.asyncio as aioredis
import sentry_sdk
from naff.models.discord.message import process_message_payload

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
    if not isinstance(error, aiohttp.ServerDisconnectedError):
        with sentry_sdk.configure_scope() as scope:
            if ctx:
                scope.set_context(
                    type(ctx).__name__,
                    {
                        "args": ctx.args,
                        "kwargs": ctx.kwargs,
                        "message": ctx.message,
                    },
                )
            sentry_sdk.capture_exception(error)

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
    string = str(content) if split else content

    str_chunks = string_split(string) if split else content
    for chunk in str_chunks:
        await bot.owner.send(f"{chunk}")


def line_split(content: str, split_by=20):
    content_split = content.splitlines()
    return [
        content_split[x : x + split_by] for x in range(0, len(content_split), split_by)
    ]


def embed_check(embed: naff.Embed) -> bool:
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


def na_friendly_str(obj: typing.Any):
    return str(obj) if obj else "N/A"


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

        config: GuildConfig = await GuildConfig.get(
            guild_id=self.guild.id
        ).prefetch_related(
            "premium_code"
        )  # type: ignore
        self.guild_config = config
        return config

    async def edit(
        self,
        content: typing.Optional[str] = None,
        embeds: typing.Optional["list[naff.Embed | dict] | naff.Embed | dict"] = None,
        embed: typing.Optional["naff.Embed | dict"] = None,
        components: typing.Optional[
            typing.Union[
                typing.List[typing.List[typing.Union["naff.BaseComponent", dict]]],
                typing.List[typing.Union["naff.BaseComponent", dict]],
                "naff.BaseComponent",
                dict,
            ]
        ] = None,
        allowed_mentions: typing.Optional[
            typing.Union[naff.AllowedMentions, dict]
        ] = None,
        attachments: typing.Optional[list[typing.Union[naff.Attachment, dict]]] = None,
        files: typing.Optional[typing.List[naff.UPLOADABLE_TYPE]] = None,
        tts: bool = False,
        flags: typing.Optional[typing.Union[int, naff.MessageFlags]] = None,
    ):
        """
        Edits the message.

        Args:
            content: Message text content.
            embeds: Embedded rich content (up to 6000 characters).
            embed: Embedded rich content (up to 6000 characters).
            components: The components to include with the message.
            allowed_mentions: Allowed mentions for the message.
            attachments: The attachments to keep, only used when editing message.
            files: Files to send, the path, bytes or File() instance, defaults to None. You may have up to 10 files.
            tts: Should this message use Text To Speech.
            flags: Message flags to apply.

        Returns:
            New message object with edits applied
        """
        message_payload = process_message_payload(
            content=content,
            embeds=embeds or embed,
            components=components,
            allowed_mentions=allowed_mentions,
            attachments=attachments,
            tts=tts,
            flags=flags,
        )

        if self.ephemeral:
            raise naff.errors.EphemeralEditException

        message_data = await self._client.http.edit_interaction_message(
            message_payload, self._client.app.id, self._token, files=files
        )
        if message_data:
            return self._client.cache.place_message_data(message_data)


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

        config: GuildConfig = await GuildConfig.get(
            guild_id=self.guild.id
        ).prefetch_related(
            "premium_code"
        )  # type: ignore
        self.guild_config = config
        return config


@naff.utils.define
class RealmAutocompleteContext(naff.AutocompleteContext):
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

        config: GuildConfig = await GuildConfig.get(
            guild_id=self.guild.id
        ).prefetch_related(
            "premium_code"
        )  # type: ignore
        self.guild_config = config
        return config


if typing.TYPE_CHECKING:
    from .custom_providers import ProfileProvider, ClubProvider
    from .realms_api import RealmsAPI
    from .classes import TimedDict
    from .help_tools import PermissionsResolver, MiniCommand

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
        online_cache: defaultdict[int, set[str]]
        realm_name_cache: TimedDict[typing.Optional[str], str]
        own_gamertag: str
        slash_perms_cache: defaultdict[int, dict[int, PermissionsResolver]]
        mini_commands_per_scope: dict[int, dict[str, MiniCommand]]
        live_playerlist_store: defaultdict[str, set[int]]

else:

    class RealmBotBase(naff.Client):
        pass


async def _global_checks(ctx: naff.Context):
    if not ctx.bot.is_ready:
        return False

    if not ctx.bot.fully_ready.is_set():  # type: ignore
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
