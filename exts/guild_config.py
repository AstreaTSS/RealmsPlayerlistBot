import asyncio
import contextlib
import importlib
import logging
import os
import re
import typing

import aiohttp
import interactions as ipy
import tansy
from msgspec import ValidationError

import common.classes as cclasses
import common.clubs_playerlist as clubs_playerlist
import common.models as models
import common.playerlist_utils as pl_utils
import common.utils as utils
from common.microsoft_core import MicrosoftAPIException
from common.xbox_api import ClubResponse

if typing.TYPE_CHECKING:
    from common.realms_api import FullRealm

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
FORMAT_CODE_REGEX = re.compile(r"§\S")


class GuildConfig(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.name = "Server Config"
        self.bot: utils.RealmBotBase = bot

    async def _gather_realm_names(self, specific_realm_id: str) -> "FullRealm | None":
        response = await self.bot.realms.fetch_realms()
        names = tuple((str(realm.id), realm.name) for realm in response.servers)
        self.bot.realm_name_cache.update(names)

        return next(
            (realm for realm in response.servers if str(realm.id) == specific_realm_id),
            None,
        )

    config = tansy.TansySlashCommand(
        name="config",
        description="Handles configuration of the bot.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @config.subcommand(
        sub_cmd_name="info",
        sub_cmd_description="Lists out the configuration settings for this server.",
    )
    async def info(self, ctx: utils.RealmContext) -> None:
        config = await ctx.fetch_config()

        embed = ipy.Embed(
            color=self.bot.color, title=f"Server Config for {ctx.guild.name}:"
        )
        playerlist_channel = (
            f"<#{config.playerlist_chan}>" if config.playerlist_chan else "N/A"
        )

        if config.realm_id:
            self.bot.realm_name_cache.expire()

            maybe_realm_name: str | None = self.bot.realm_name_cache.get(
                config.realm_id
            )
            if not maybe_realm_name and config.club_id:
                resp_bytes = await clubs_playerlist.realm_club_bytes(
                    self.bot, config.club_id
                )

                if resp_bytes:
                    with contextlib.suppress(ValidationError):
                        club = ClubResponse.from_bytes(resp_bytes)
                        maybe_realm_name = club.clubs[0].profile.name.value

                        if maybe_realm_name:
                            self.bot.realm_name_cache[config.realm_id] = (
                                maybe_realm_name
                            )

            if not maybe_realm_name:
                realm = await self._gather_realm_names(config.realm_id)

                if realm:
                    maybe_realm_name = realm.name
                    if config.club_id != str(realm.club_id):
                        config.club_id = str(realm.club_id)
                        await config.save()

            if maybe_realm_name:
                maybe_realm_name = FORMAT_CODE_REGEX.sub("", maybe_realm_name)

            realm_name = utils.na_friendly_str(maybe_realm_name)
        else:
            realm_name = "N/A"

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

        if not config.valid_premium and (
            config.live_playerlist or config.fetch_devices or config.live_online_channel
        ):
            await pl_utils.invalidate_premium(self.bot, config)

        embed.description = (
            f"Realm Name: {realm_name}\nAutorunner: {autorunner}\nAutorun Playerlist"
            f" Channel: {playerlist_channel}\nOffline Realm Ping Role:"
            f" {offline_realm_ping}\n\nPremium Activated:"
            f" {utils.yesno_friendly_str(config.valid_premium)}\nLive Playerlist:"
            f" {utils.toggle_friendly_str(config.live_playerlist)}\nFetch Devices:"
            f" {utils.toggle_friendly_str(config.fetch_devices)}"
        )

        embeds: list[ipy.Embed] = []

        if realm_not_found:
            warning_embed = ipy.Embed(
                title="Warning!",
                description=(
                    "There is a Realm ID associated with this Realm, but I could not"
                    " find the Realm itself. This may just be a problem that resolves"
                    " itself, but check that you haven't switched Realms or"
                    f" kicked the account `{self.bot.own_gamertag}`. If you did, try"
                    f" relinking the Realm via {self.link_realm.mention()}.\nFor more"
                    " information, please check"
                    " https://rpl.astrea.cc/wiki/faq.html#help-the-playerlist-online-command-isn-t-working."
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
            raise ipy.errors.BadArgument(
                "You must either give a realm code/link or explictly unlink your Realm."
                " One must be given."
            )

        config = await ctx.fetch_config()

        if _realm_code:
            realm_code_matches = REALMS_LINK_REGEX.fullmatch(_realm_code)

            if not realm_code_matches:
                raise ipy.errors.BadArgument("Invalid Realm code!")

            realm_code = realm_code_matches[1]

            try:
                realm = await ctx.bot.realms.join_realm_from_code(realm_code)

                config.realm_id = str(realm.id)
                self.bot.realm_name_cache[config.realm_id] = realm.name

                embeds: list[ipy.Embed] = []

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
                    warning_embed = ipy.Embed(
                        title="Warning",
                        description=(
                            "I was unable to backfill player data for this Realm. If"
                            f" you use {self.bot.mention_cmd('playerlist')}, it may"
                            " show imcomplete player data. This should resolve itself"
                            " in about 24 hours."
                        ),
                        color=ipy.RoleColors.YELLOW,
                    )
                    embeds.append(warning_embed)

                await config.save()

                confirm_embed = ipy.Embed(
                    title="Linked!",
                    description=(
                        "Linked this server to the Realm:"
                        f" `{realm.name}`\n\n**IMPORTANT NOTE:** There will now be an"
                        f" account called `{self.bot.own_gamertag}` on your Realm's"
                        " player roster (and even the playerlist). *Do not ban or kick"
                        " them.* The bot will not work with your Realm if you do so."
                    ),
                    color=ipy.RoleColors.GREEN,
                )
                embeds.append(confirm_embed)
                await ctx.send(embeds=embeds)
            except MicrosoftAPIException as e:
                if (
                    isinstance(e.error, aiohttp.ClientResponseError)
                    and e.resp.status == 403
                ):
                    raise ipy.errors.BadArgument(
                        "I could not join this Realm. Please make sure the Realm code"
                        " is spelled correctly, and that the code is valid. Also make"
                        " sure that you have not banned or kicked"
                        f" `{self.bot.own_gamertag}` from the Realm."
                    ) from None
                else:
                    raise
        else:
            if not config.realm_id:
                raise utils.CustomCheckFailure("There's no Realm to unlink!")

            realm_id = config.realm_id

            config.realm_id = None
            config.club_id = None
            config.live_playerlist = False
            config.fetch_devices = False
            config.live_online_channel = None

            await config.save()

            await ctx.send("Unlinked Realm.")

            self.bot.live_playerlist_store[realm_id].discard(config.guild_id)
            await self.bot.redis.delete(f"invalid-playerlist3-{config.guild_id}")
            await self.bot.redis.delete(f"invalid-playerlist7-{config.guild_id}")

            if not await models.GuildConfig.filter(
                realm_id=realm_id, fetch_devices=True
            ).exists():
                self.bot.fetch_devices_for.discard(realm_id)

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

                self.bot.offline_realms.discard(int(realm_id))
                self.bot.dropped_offline_realms.discard(int(realm_id))
                await self.bot.redis.delete(f"missing-realm-{realm_id}")
                await self.bot.redis.delete(f"invalid-realmoffline-{realm_id}")

    @config.subcommand(
        sub_cmd_name="playerlist-channel",
        sub_cmd_description="Sets (or unsets) where the autorun playerlist is sent to.",
    )
    async def set_playerlist_channel(
        self,
        ctx: utils.RealmContext,
        channel: typing.Optional[ipy.GuildText] = tansy.Option(
            "The channel to set the playerlist to.",
            converter=cclasses.ValidChannelConverter,
        ),
        unset: bool = tansy.Option("Should the channel be unset?", default=False),
    ) -> None:
        # xors, woo!
        if not (unset ^ bool(channel)):
            raise ipy.errors.BadArgument(
                "You must either set a channel or explictly unset the channel. One must"
                " be given."
            )

        config = await ctx.fetch_config()

        if channel:
            if typing.TYPE_CHECKING:
                assert isinstance(channel, ipy.GuildText)  # noqa: S101

            config.playerlist_chan = channel.id
            await config.save()
            await self.bot.redis.delete(
                f"invalid-playerlist3-{config.guild_id}",
                f"invalid-playerlist7-{config.guild_id}",
            )

            await ctx.send(f"Set the playerlist channel to {channel.mention}.")
        else:
            if not config.playerlist_chan:
                raise utils.CustomCheckFailure(
                    "There was no channel set in the first place."
                )

            config.playerlist_chan = None
            await config.save()
            await self.bot.redis.delete(
                f"invalid-playerlist3-{config.guild_id}",
                f"invalid-playerlist7-{config.guild_id}",
            )

            if config.realm_id:
                self.bot.live_playerlist_store[config.realm_id].discard(config.guild_id)

            await ctx.send("Unset the playerlist channel.")

    @staticmethod
    def button_check(author_id: int) -> typing.Callable[..., bool]:
        def _check(event: ipy.events.Component) -> bool:
            return event.ctx.author.id == author_id

        return _check

    @config.subcommand(
        sub_cmd_name="toggle-realm-warning",
        sub_cmd_description=(
            "Toggles if the warning that is sent after no activity is detected in the"
            " Realm is sent."
        ),
    )
    async def toggle_realm_warning(
        self,
        ctx: utils.RealmContext,
        toggle: bool = tansy.Option("Should the warning be sent?"),
    ) -> None:
        """
        Toggles if the warning that is sent after no activity is detected in the Realm is sent.
        This warning is usually sent after 24 hours of no activity has been detected.
        This is usually beneficial, but may be annoying if you have a Realm that is rarely used.

        Do note that the Realm will still be unlinked after 7 days of inactivity, regardless of this.
        """

        config = await ctx.fetch_config()

        if config.warning_notifications == toggle:
            raise ipy.errors.BadArgument("That's already the current setting.")

        if not toggle:
            embed = ipy.Embed(
                title="Warning",
                description=(
                    "This warning is usually a very important warning. If the bot"
                    " cannot find any players on the Realm after 24 hours, this"
                    " usually means that either the Realm is down, and so the"
                    " playerlist should be turned off, or that"
                    f" `{self.bot.own_gamertag}` has been kicked/banned, preventing the"
                    " bot from functioning. **You should not disable this warning"
                    " lightly, as it could be critical to fixing issues with the"
                    " bot.**\n**Also note that the Realm will still be unlinked after"
                    " 7 days of inactivity. It is your responsibility to keep track of"
                    " this.**\nDisabling these warnings may still be beneficial if"
                    " your Realm isn't as active, though, as long as you are aware of"
                    " the risks.\n\n**If you wish to continue to silence these"
                    " warnings, press the accept button.** You have two minutes to"
                    " do so."
                ),
                timestamp=ipy.Timestamp.utcnow(),
                color=ipy.RoleColors.YELLOW,
            )

            result = ""
            event = None

            components = [
                ipy.Button(style=ipy.ButtonStyle.GREEN, label="Accept", emoji="✅"),
                ipy.Button(style=ipy.ButtonStyle.RED, label="Decline", emoji="✖️"),
            ]
            msg = await ctx.send(embed=embed, components=components)

            try:
                event = await self.bot.wait_for_component(
                    msg, components, self.button_check(ctx.author.id), timeout=120
                )

                if event.ctx.custom_id == components[1].custom_id:
                    result = "Declined disabling the warnings."
                else:
                    config.warning_notifications = False
                    await config.save()

                    result = "Disabled the warnings."
            except asyncio.TimeoutError:
                result = "Timed out."
            finally:
                if event:
                    await event.ctx.send(
                        result,
                        ephemeral=True,
                        allowed_mentions=ipy.AllowedMentions.none(),
                    )
                await ctx.edit(msg, content=result, embeds=[], embed=[], components=[])  # type: ignore

        else:
            config.warning_notifications = True
            await config.save()

            await ctx.send("Enabled the warnings.")

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
        role: typing.Optional[ipy.Role] = tansy.Option("The role to use for the ping."),
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
            raise ipy.errors.BadArgument(
                "You must either set a role or explictly unset the role. One must be"
                " given."
            )

        config = await ctx.fetch_config()

        if role:
            if isinstance(role, str):  # ???
                role = await ctx.guild.fetch_role(role)

            if (
                not role.mentionable
                and ipy.Permissions.MENTION_EVERYONE not in ctx.app_permissions
            ):
                raise utils.CustomCheckFailure(
                    "I cannot ping this role. Make sure the role is either mentionable"
                    " or the bot can mention all roles."
                )

            if not config.realm_id:
                raise utils.CustomCheckFailure(
                    "Please link your Realm with this server with"
                    f" {self.link_realm.mention()} first."
                )

            if not config.playerlist_chan:
                raise utils.CustomCheckFailure(
                    "Please set up the autorunner with"
                    f" {self.set_playerlist_channel.mention()} first."
                )

            embed = ipy.Embed(
                title="Warning",
                description=(
                    "This ping won't be 100% accurate. The ping hooks onto an event"
                    ' where the Realm "disappears" from the bot\'s perspective, which'
                    " happens for a variety of reasons, like crashing... or sometimes,"
                    " when no one is on the server. Because of this, *it is recommended"
                    " that this is only enabled for large Realms.*\n\n**If you wish to"
                    " continue with adding the role, press the accept button.** You"
                    " have one minute to do so."
                ),
                timestamp=ipy.Timestamp.utcnow(),
                color=ipy.RoleColors.YELLOW,
            )

            result = ""
            event = None

            components = [
                ipy.Button(style=ipy.ButtonStyle.GREEN, label="Accept", emoji="✅"),
                ipy.Button(style=ipy.ButtonStyle.RED, label="Decline", emoji="✖️"),
            ]
            msg = await ctx.send(embed=embed, components=components)

            try:
                event = await self.bot.wait_for_component(
                    msg, components, self.button_check(ctx.author.id), timeout=60
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
                        allowed_mentions=ipy.AllowedMentions.none(),
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
