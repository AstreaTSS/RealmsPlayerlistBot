import importlib
import os
import re
import typing

import aiohttp
import naff

import common.classes as cclasses
import common.clubs_playerlist as clubs_playerlist
import common.utils as utils
from common.realms_api import RealmsAPIException


# regex that takes in:
# - https://realms.gg/XXXXXXX
# - https://open.minecraft.net/pocket/realms/invite/XXXXXXX
# - minecraft://acceptRealmInvite?inviteID=XXXXXXX
# - XXXXXXX

# where XXXXXXX is a string that only can have:
# - the alphabet, lower and upper
# - numbers
# - underscores and dashes
REALMS_LINK_REGEX = re.compile(
    r"(?:http:|https:\/\/)?(?:www\.)?realms\.gg\/([a-zA-Z0-9_-]{7,16})|(?:http:|https:\/\/)"
    r"?open\.minecraft\.net\/pocket\/realms\/invite\/([a-zA-Z0-9_-]{7,16})|(?:minecraft:\/\/)"
    r"?acceptRealmInvite\?inviteID=([a-zA-Z0-9_-]{7,16})|([a-zA-Z0-9_-]{7,16})"
)


class GuildConfig(utils.Extension):
    def __init__(self, bot):
        self.name = "Server Config"
        self.bot: utils.RealmBotBase = bot

    async def _gather_realm_names(self):
        response = await self.bot.realms.fetch_realms()
        name_dict = {str(realm.id): realm.name for realm in response.servers}
        self.bot.realm_name_cache.insert(name_dict)  # type: ignore

    config = naff.SlashCommand(
        name="config",  # type: ignore
        description="Handles configuration of the bot.",  # type: ignore
        default_member_permissions=naff.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @config.subcommand(
        sub_cmd_name="info",
        sub_cmd_description="Lists out the configuration settings for this server.",
    )
    async def info(self, ctx: utils.RealmContext):
        config = await ctx.fetch_config()

        embed = naff.Embed(
            color=self.bot.color, title=f"Server Config for {ctx.guild.name}:"
        )
        playerlist_channel = (
            f"<#{config.playerlist_chan}> (ID: {config.playerlist_chan})"
            if config.playerlist_chan
            else "N/A"
        )

        if self.bot.realm_name_cache.empty:
            await self._gather_realm_names()

        realm_name = utils.na_friendly_str(
            self.bot.realm_name_cache.get(config.realm_id)
        )
        if realm_name != "N/A":
            realm_name = f"`{realm_name}`"

        autorunner = utils.toggle_friendly_str(
            bool(config.club_id and config.realm_id and config.playerlist_chan)
        )

        embed.description = (
            f"Autorun Playerlist Channel: {playerlist_channel}\nRealm Name:"
            f" {realm_name}\nAutorunner: {autorunner}\nPremium Activated:"
            f" {utils.yesno_friendly_str(bool(config.premium_code))}\n\nExtra"
            f" Info:\nRealm ID: {utils.na_friendly_str(config.realm_id)}\nClub ID:"
            f" {utils.na_friendly_str(config.club_id)}"
        )
        await ctx.send(embed=embed)

    @config.subcommand(
        sub_cmd_name="link-realm",
        sub_cmd_description=(
            "Links a realm to this server via a realm code. This overwrites the old"
            " Realm stored."
        ),
    )
    @naff.slash_option(
        "realm-code",
        "The Realm code or link.",
        naff.OptionTypes.STRING,
        required=True,
    )
    async def link_realm(self, ctx: utils.RealmContext, **kwargs):
        config = await ctx.fetch_config()
        _realm_code: str = kwargs["realm-code"]

        realm_code_matches = REALMS_LINK_REGEX.match(_realm_code)

        if not realm_code_matches:
            raise naff.errors.BadArgument("Invalid Realm code!")

        realm_code = next(
            (g for g in realm_code_matches.groups() if g is not None), None
        )

        if not realm_code:
            raise naff.errors.BadArgument("Invalid Realm code!")

        try:
            realm = await ctx.bot.realms.join_realm_from_code(realm_code)

            config.realm_id = str(realm.id)
            config.club_id = str(realm.club_id)
            self.bot.realm_name_cache.add_one(config.realm_id, realm.name)
            await clubs_playerlist.fill_in_data_from_clubs(
                self.bot, config.realm_id, config.club_id
            )

            await config.save()
            await ctx.send(f"Linked this server to the Realm: `{realm.name}`.")
        except RealmsAPIException as e:
            if (
                isinstance(e.error, aiohttp.ClientResponseError)
                and e.resp.status == 403
            ):
                raise naff.errors.BadArgument(
                    "Invalid Realm code. Please make sure the Realm code is spelled"
                    " correctly, and that the code is valid."
                )
            else:
                raise

    @config.subcommand(
        sub_cmd_name="set-playerlist-channel",
        sub_cmd_description="Sets where the autorun playerlist is sent to.",
    )
    @naff.slash_option(
        "channel",
        "The channel to set the playerlist to.",
        naff.OptionTypes.CHANNEL,
        required=True,
        channel_types=[naff.ChannelTypes.GUILD_TEXT],
    )
    async def set_playerlist_channel(
        self,
        ctx: utils.RealmContext,
        channel: typing.Annotated[naff.GuildText, cclasses.ValidChannelConverter],
    ):
        config = await ctx.fetch_config()
        config.playerlist_chan = channel.id
        await config.save()

        await ctx.send(f"Set the playerlist channel to {channel.mention}.")

    @config.subcommand(
        sub_cmd_name="unset-playerlist-channel",
        sub_cmd_description="Unsets the autorun playerlist channel.",
    )
    async def unset_playerlist_channel(
        self,
        ctx: utils.RealmContext,
    ):
        config = await ctx.fetch_config()
        config.playerlist_chan = None
        await config.save()

        await ctx.send("Unset the playerlist channel.")

    @config.subcommand(
        sub_cmd_name="help",
        sub_cmd_description="Tells you how to set up this bot.",
    )
    async def setup_help(
        self,
        ctx: utils.RealmContext,
    ):
        await ctx.send(os.environ["SETUP_LINK"])


def setup(bot):
    importlib.reload(utils)
    importlib.reload(clubs_playerlist)
    importlib.reload(cclasses)
    GuildConfig(bot)