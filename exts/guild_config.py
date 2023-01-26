import asyncio
import collections
import importlib
import logging
import os
import re
import typing

import aiohttp
import naff
import tansy

import common.classes as cclasses
import common.clubs_playerlist as clubs_playerlist
import common.models as models
import common.utils as utils
from common.microsoft_core import MicrosoftAPIException

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
    r"(?:(?:https?://)?(?:www\.)?realms\.gg/|(?:https?://)?open\.minecraft"
    r"\.net/pocket/realms/invite/|(?:minecraft://)?acceptRealmInvite\?inviteID="
    r")?([\w-]{7,16})"
)


class GuildConfig(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.name = "Server Config"
        self.bot: utils.RealmBotBase = bot

    async def _gather_realm_names(self) -> None:
        response = await self.bot.realms.fetch_realms()
        name_dict = {str(realm.id): realm.name for realm in response.servers}
        self.bot.realm_name_cache.insert(name_dict)  # type: ignore

    config = tansy.TansySlashCommand(
        name="config",
        description="Handles configuration of the bot.",  # type: ignore
        default_member_permissions=naff.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @config.subcommand(
        sub_cmd_name="info",
        sub_cmd_description="Lists out the configuration settings for this server.",
    )
    async def info(self, ctx: utils.RealmContext) -> None:
        config = await ctx.fetch_config()

        embed = naff.Embed(
            color=self.bot.color, title=f"Server Config for {ctx.guild.name}:"
        )
        playerlist_channel = (
            f"<#{config.playerlist_chan}> (ID: {config.playerlist_chan})"
            if config.playerlist_chan
            else "N/A"
        )

        if not self.bot.realm_name_cache.filled:
            await self._gather_realm_names()

        realm_name = utils.na_friendly_str(
            self.bot.realm_name_cache.get(config.realm_id)
        )
        realm_not_found = False
        if realm_name != "N/A":
            realm_name = f"`{realm_name}`"
        elif config.realm_id:
            realm_not_found = True
            realm_name = "Not Found"

        autorunner = utils.toggle_friendly_str(
            bool(config.realm_id and config.playerlist_chan)
        )
        offline_realm_ping = (
            f"<@&{config.realm_offline_role}>" if config.realm_offline_role else "N/A"
        )

        embed.description = (
            f"Realm Name: {realm_name}\nAutorunner: {autorunner}\nAutorun Playerlist"
            f" Channel: {playerlist_channel}\nOffline Realm Ping Role:"
            f" {offline_realm_ping}\n\nPremium Activated:"
            f" {utils.yesno_friendly_str(bool(config.premium_code))}\nLive Playerlist:"
            f" {utils.toggle_friendly_str(config.live_playerlist)}"
        )

        embeds: list[naff.Embed] = []

        if realm_not_found:
            warning_embed = naff.Embed(
                title="Warning!",
                description=(
                    "There is a Realm ID associated with this Realm, but I could not"
                    " find the Realm itself. This may just be a problem that resolves"
                    " itself, but check that you haven't switched Realms or"
                    f" kicked the account `{self.bot.own_gamertag}`. If you did, try"
                    f" relinking the Realm via {self.link_realm.mention()}.\nFor more"
                    " information, please check"
                    " https://github.com/AstreaTSS/RealmsPlayerlistBot/wiki/FAQ#help-"
                    "the-playerlistonline-comamnd-isnt-working."
                ),
            )
            embeds.append(warning_embed)
        embeds.append(embed)

        await ctx.send(embeds=embeds)

    @config.subcommand(
        sub_cmd_name="link-realm",
        sub_cmd_description=(
            "Links (or unlinks) a realm to this server via a realm code. This"
            " overwrites the old Realm stored."
        ),
    )
    async def link_realm(
        self,
        ctx: utils.RealmContext,
        _realm_code: typing.Optional[str] = tansy.Option(
            "The Realm code or link.", name="realm_code", default=None
        ),
        unlink: bool = tansy.Option(
            (
                "Should the Realm be unlinked from this server? Do not set this if you"
                " are linking your Realm."
            ),
            default=False,
        ),
    ) -> None:
        if not (unlink ^ bool(_realm_code)):
            raise naff.errors.BadArgument(
                "You must either give a realm code/link or explictly unlink your Realm."
                " One must be given."
            )

        config = await ctx.fetch_config()

        if _realm_code:
            realm_code_matches = REALMS_LINK_REGEX.fullmatch(_realm_code)

            if not realm_code_matches:
                raise naff.errors.BadArgument("Invalid Realm code!")

            realm_code = realm_code_matches[1]

            try:
                realm = await ctx.bot.realms.join_realm_from_code(realm_code)

                config.realm_id = str(realm.id)
                self.bot.realm_name_cache.add_one(config.realm_id, realm.name)

                embeds: collections.deque[naff.Embed] = collections.deque()

                if (
                    realm.club_id
                    and not await models.PlayerSession.filter(
                        realm_id=realm.id
                    ).exists()
                ):
                    config.club_id = str(realm.club_id)
                    await clubs_playerlist.fill_in_data_from_clubs(
                        self.bot, config.realm_id, config.club_id
                    )
                else:
                    warning_embed = naff.Embed(
                        title="Warning",
                        description=(
                            "I was unable to backfill player data for this Realm. If"
                            f" you use {self.bot.mention_cmd('playerlist')}, it may"
                            " show imcomplete player data. This should resolve itself"
                            " in about 24 hours."
                        ),
                        color=naff.RoleColors.YELLOW,
                    )
                    embeds.appendleft(warning_embed)

                await config.save()

                confirm_embed = naff.Embed(
                    title="Linked!",
                    description=(
                        "Linked this server to the Realm:"
                        f" `{realm.name}`\n\n**IMPORTANT NOTE:** There will now be an"
                        f" account called `{self.bot.own_gamertag}` on your Realm's"
                        " player roster (and even the playerlist). *Do not ban or kick"
                        " them.* The bot will not work with your Realm if you do so."
                    ),
                    color=naff.RoleColors.GREEN,
                )
                embeds.appendleft(confirm_embed)
                await ctx.send(embeds=list(embeds))
            except MicrosoftAPIException as e:
                if (
                    isinstance(e.error, aiohttp.ClientResponseError)
                    and e.resp.status == 403
                ):
                    raise naff.errors.BadArgument(
                        "Invalid Realm code. Please make sure the Realm code is spelled"
                        " correctly, and that the code is valid."
                    ) from None
                else:
                    raise
        else:
            if not config.realm_id:
                raise utils.CustomCheckFailure("There's no Realm to unlink!")

            realm_id = config.realm_id

            config.realm_id = None
            config.club_id = None
            config.playerlist_chan = None
            config.realm_offline_role
            config.live_playerlist = False

            await config.save()

            await ctx.send("Unlinked Realm.")

            if not await models.GuildConfig.filter(realm_id=realm_id).exists():
                try:
                    await self.bot.realms.leave_realm(realm_id)
                except MicrosoftAPIException as e:
                    # might be an invalid id somehow? who knows
                    if e.resp.status == 404:
                        logging.getLogger("realms_bot").warning(
                            f"Could not leave Realm with ID {realm_id}."
                        )
                    else:
                        raise

                self.bot.offline_realm_time.pop(int(realm_id), None)

    @config.subcommand(
        sub_cmd_name="playerlist-channel",
        sub_cmd_description="Sets (or unsets) where the autorun playerlist is sent to.",
    )
    async def set_playerlist_channel(
        self,
        ctx: utils.RealmContext,
        channel: typing.Optional[naff.GuildText] = tansy.Option(
            "The channel to set the playerlist to.",
            converter=cclasses.ValidChannelConverter,
        ),
        unset: bool = tansy.Option("Should the channel be unset?", default=False),
    ) -> None:
        # xors, woo!
        if not (unset ^ bool(channel)):
            raise naff.errors.BadArgument(
                "You must either set a channel or explictly unset the channel. One must"
                " be given."
            )

        config = await ctx.fetch_config()

        if channel:
            if typing.TYPE_CHECKING:
                assert isinstance(channel, naff.GuildText)  # noqa: S101

            config.playerlist_chan = channel.id
            await config.save()
            await self.bot.redis.delete(f"invalid-playerlist-{config.guild_id}")

            await ctx.send(f"Set the playerlist channel to {channel.mention}.")
        else:
            if not config.playerlist_chan:
                raise utils.CustomCheckFailure(
                    "There was no channel set in the first place."
                )

            config.playerlist_chan = None
            await config.save()
            await self.bot.redis.delete(f"invalid-playerlist-{config.guild_id}")

            if config.realm_id:
                self.bot.live_playerlist_store[config.realm_id].discard(config.guild_id)

            await ctx.send("Unset the playerlist channel.")

    @staticmethod
    def button_check(author_id: int) -> typing.Callable[..., bool]:
        def _check(event: naff.events.Component) -> bool:
            return event.ctx.author.id == author_id

        return _check

    @config.subcommand(
        sub_cmd_name="realm-offline-role",
        sub_cmd_description=(
            "Sets (or unsets) the role that should be pinged in the autorunner channel"
            " if the Realm goes offline."
        ),
    )
    async def set_realm_offline_role(
        self,
        ctx: utils.RealmContext,
        role: typing.Optional[naff.Role] = tansy.Option(
            "The role to use for the ping."
        ),
        unset: bool = tansy.Option("Should the role be unset?", default=False),
    ) -> None:
        """
        Sets (or unsets) the role that should be pinged in the autorunner channel if the Realm goes offline.
        This may be unreliable due to how it's made - it works best in large Realms that \
        rarely have 0 players, and may trigger too often otherwise.

        The bot must be linked to a Realm and the autorunner channel must be set for this to work.
        The bot also must be able to ping the role.

        You must either set a role or explictly unset the role. Only one of the two may (and must) be given.
        """
        # xors, woo!
        if not (unset ^ bool(role)):
            raise naff.errors.BadArgument(
                "You must either set a role or explictly unset the role. One must be"
                " given."
            )

        config = await ctx.fetch_config()

        if role:
            if (
                not role.mentionable
                and naff.Permissions.MENTION_EVERYONE
                not in ctx.channel.permissions_for(ctx.guild.me)
            ):
                raise utils.CustomCheckFailure(
                    "I cannot ping this role. Make sure the role is either mentionable"
                    " or the bot can mention all roles."
                )

            if not config.realm_id or not config.club_id:
                raise utils.CustomCheckFailure(
                    "Please link your Realm with this server with"
                    f" {self.link_realm.mention()} first."
                )

            if not config.playerlist_chan:
                raise utils.CustomCheckFailure(
                    "Please set up the autorunner with"
                    f" {self.set_playerlist_channel.mention()} first."
                )

            embed = naff.Embed(
                title="Warning",
                description=(
                    "This ping won't be 100% accurate. The ping hooks onto an event"
                    ' where the Realm "disappears" from the bot\'s perspective, which'
                    " happens for a variety of reasons, like crashing... or sometimes,"
                    " when no one is on the server. Because of this, *it is recommended"
                    " that this is only enabled for large Realms.*\n\n**If you wish to"
                    " continue with adding the role, press the accept button.** You"
                    " have 30 seconds to do so."
                ),
                timestamp=naff.Timestamp.utcnow(),
                color=naff.RoleColors.YELLOW,
            )

            result = ""
            event = None

            components = [
                naff.Button(naff.ButtonStyles.GREEN, "Accept", "✅"),
                naff.Button(naff.ButtonStyles.RED, "Decline", "✖️"),
            ]
            msg = await ctx.send(embed=embed, components=components)

            try:
                event = await self.bot.wait_for_component(
                    msg, components, self.button_check(ctx.author.id), timeout=30
                )

                if event.ctx.custom_id == components[1].custom_id:
                    result = "Declined setting the Realm offline ping."
                else:
                    config.realm_offline_role = role.id
                    await config.save()

                    result = f"Set the Realm offline ping to {role.mention}."
            except asyncio.TimeoutError:
                result = "Timed out."
            finally:
                if event:
                    await event.ctx.send(
                        result,
                        ephemeral=True,
                        allowed_mentions=naff.AllowedMentions.none(),
                    )
                await ctx.edit(msg, content=result, embeds=[], embed=[], components=[])  # type: ignore
        else:
            if not config.realm_offline_role:
                raise utils.CustomCheckFailure(
                    "There was no role set in the first place."
                )

            config.realm_offline_role = None
            await config.save()
            await ctx.send("Unset the Realm offline ping role.")

    @config.subcommand(
        sub_cmd_name="help",
        sub_cmd_description="Tells you how to set up this bot.",
    )
    async def setup_help(
        self,
        ctx: utils.RealmContext,
    ) -> None:
        await ctx.send(os.environ["SETUP_LINK"])


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(clubs_playerlist)
    importlib.reload(cclasses)
    GuildConfig(bot)
