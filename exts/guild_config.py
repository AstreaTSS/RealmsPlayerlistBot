import asyncio
import importlib
import logging
import os
import re
import typing

import aiohttp
import elytra
import interactions as ipy
import tansy

import common.classes as cclasses
import common.clubs_playerlist as clubs_playerlist
import common.device_code as device_code
import common.models as models
import common.playerlist_utils as pl_utils
import common.utils as utils

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


logger = logging.getLogger("realms_bot")


class GuildConfig(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.name = "Server Config"
        self.bot: utils.RealmBotBase = bot

    async def _gather_realm_names(
        self, specific_realm_id: str
    ) -> elytra.FullRealm | None:
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
    async def info(
        self,
        ctx: utils.RealmContext,
        diagnostic_info: bool = tansy.Option(
            "Additionally adds on extra information useful for diagnostics and bot"
            " development.",
            default=False,
        ),
    ) -> None:
        config = await ctx.fetch_config()

        if config.realm_id:
            self.bot.realm_name_cache.expire()

            maybe_realm_name: str | None = self.bot.realm_name_cache.get(
                config.realm_id
            )
            if not maybe_realm_name and config.club_id:
                club_resp = await clubs_playerlist.realm_club_presence(
                    self.bot, config.club_id
                )

                if club_resp:
                    maybe_realm_name = club_resp.clubs[0].profile.name.value

                    if maybe_realm_name:
                        self.bot.realm_name_cache[config.realm_id] = maybe_realm_name

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

        if not config.premium_code and (
            config.live_playerlist or config.fetch_devices or config.live_online_channel
        ):
            await pl_utils.invalidate_premium(self.bot, config)

        embed = await utils.config_info_generate(
            ctx, config, realm_name, diagnostic_info=diagnostic_info
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

    async def add_realm(
        self,
        ctx: utils.RealmContext,
        realm: elytra.FullRealm,
        *,
        alternative_link: bool = False,
    ) -> list[ipy.Embed]:
        config = await ctx.fetch_config()

        config.realm_id = str(realm.id)
        self.bot.realm_name_cache[config.realm_id] = realm.name

        # you may think this is weird, but if a realm is actually offline when it's
        # linked, the bot has no way of ever figuring that out, and so the bot will
        # never warn about the realm at all
        # if it is online though, it'll quickly be removed from the set, so this works
        # out well enough
        self.bot.offline_realms.add(realm.id)

        embeds: list[ipy.Embed] = []

        if realm.club_id and not await models.PlayerSession.prisma().count(
            where={"realm_id": str(realm.id)}
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
        if alternative_link:
            if typing.TYPE_CHECKING:
                assert isinstance(confirm_embed.description, str)

            confirm_embed.description += (
                "\n\nAs the bot has been linked to your Realm, there is no need to"
                " continue to have the Microsoft application associated with it linked"
                " to your account.\nWhile it's not necessary, if you wish to revoke"
                " its access from your account, you can do so by going to"
                ' https://account.live.com/consent/Manage, clicking "Edit" on the'
                ' Realms Playerlist Bot application, and clicking "Remove these'
                ' permissions".'
            )

        embeds.append(confirm_embed)
        return embeds

    async def remove_realm(self, ctx: utils.RealmContext) -> None:
        config = await ctx.fetch_config()

        realm_id = config.realm_id

        config.realm_id = None
        config.club_id = None
        config.live_playerlist = False
        config.fetch_devices = False
        config.live_online_channel = None
        old_player_watchlist = config.player_watchlist
        config.player_watchlist = []
        config.player_watchlist_role = None

        await config.save()

        if not realm_id:
            return

        self.bot.live_playerlist_store[realm_id].discard(config.guild_id)
        await self.bot.redis.delete(
            f"invalid-playerlist3-{config.guild_id}",
            f"invalid-playerlist7-{config.guild_id}",
        )

        if old_player_watchlist:
            for player_xuid in old_player_watchlist:
                self.bot.player_watchlist_store[f"{realm_id}-{player_xuid}"].discard(
                    config.guild_id
                )

        if not await models.GuildConfig.prisma().count(
            where={"realm_id": realm_id, "fetch_devices": True}
        ):
            self.bot.fetch_devices_for.discard(realm_id)

        if not await models.GuildConfig.prisma().count(where={"realm_id": realm_id}):
            try:
                await self.bot.realms.leave_realm(realm_id)
            except elytra.MicrosoftAPIException as e:
                # might be an invalid id somehow? who knows
                if e.resp.status == 404:
                    logger.warning(f"Could not leave Realm with ID {realm_id}.")
                else:
                    raise

            self.bot.offline_realms.discard(int(realm_id))
            self.bot.dropped_offline_realms.discard(int(realm_id))
            await self.bot.redis.delete(
                f"missing-realm-{realm_id}", f"invalid-realmoffline-{realm_id}"
            )

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
            "Should the Realm be unlinked from this server? Do not set this if you"
            " are linking your Realm.",
            default=False,
        ),
    ) -> None:
        if not (unlink ^ bool(_realm_code)):
            raise ipy.errors.BadArgument(
                "You must either give a realm code/link or explictly unlink your Realm."
                " One must be given."
            )

        config = await ctx.fetch_config()

        if unlink and not config.realm_id:
            raise utils.CustomCheckFailure("There's no Realm to unlink!")

        if unlink:
            await self.remove_realm(ctx)
            await ctx.send(embeds=utils.make_embed("Unlinked the Realm."))
            return

        if not _realm_code:
            raise utils.CustomCheckFailure(
                "This should never happen. If it does, join the support server and"
                " report this."
            )

        realm_code_matches = REALMS_LINK_REGEX.fullmatch(_realm_code)

        if not realm_code_matches:
            raise ipy.errors.BadArgument("Invalid Realm code!")

        realm_code = realm_code_matches[1]

        try:
            realm = await ctx.bot.realms.join_realm_from_code(realm_code)

            if config.realm_id != str(realm.id):
                await self.remove_realm(ctx)

            embeds = await self.add_realm(ctx, realm)
            await ctx.send(embeds=embeds)
        except elytra.MicrosoftAPIException as e:
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

    @config.subcommand(
        sub_cmd_name="alternate-link",
        sub_cmd_description=(
            "An alternate way to link a Realm to this server. Requires being the"
            " Realm owner."
        ),
    )
    @ipy.auto_defer(enabled=True, ephemeral=True)
    async def alternate_link(self, ctx: utils.RealmContext) -> None:
        config = await ctx.fetch_config()

        embed = ipy.Embed(
            title="Warning",
            description=(
                "**This method requires signing into and giving brief access to your"
                " Microsoft/Xbox account.**\nThe bot will only use this to get your"
                " Realms and add the bot's account to said Realm - the bot will not"
                " store your credientials. However, you may feel uncomfortable with"
                f" this. If so, you can use {self.link_realm.mention()} to link your"
                " Realm, though that requires a Realm code (even temporarily).\n\n**If"
                " you wish to continue, click the accept button below.** You have two"
                " minutes to do so."
            ),
            timestamp=ipy.Timestamp.utcnow(),
            color=ipy.RoleColors.YELLOW,
        )

        success = False
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
                result = "Declined linking the Realm through this method."
            else:
                result = "Loading..."
                success = True
        except asyncio.TimeoutError:
            result = "Timed out."
        finally:
            embed = utils.make_embed(result)
            await ctx.edit(msg, embeds=embed, components=[])

        if not success:
            return

        try:
            oauth = await device_code.handle_flow(ctx, msg)
            realm = await device_code.handle_realms(ctx, msg, oauth)
        except ipy.errors.HTTPException as e:
            if e.status == 404:
                # probably just cant edit embed because it was dismissed
                return
            raise

        if config.realm_id != str(realm.id):
            await self.remove_realm(ctx)

        embeds = await self.add_realm(ctx, realm, alternative_link=True)
        await ctx.edit(msg, embeds=embeds, components=[])

    @config.subcommand(
        sub_cmd_name="playerlist-channel",
        sub_cmd_description="Sets (or unsets) where the autorun playerlist is sent to.",
    )
    @ipy.check(pl_utils.has_linked_realm)
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

            await ctx.send(
                embeds=utils.make_embed(
                    f"Set the playerlist channel to {channel.mention}."
                )
            )
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

            await ctx.send(embeds=utils.make_embed("Unset the playerlist channel."))

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
    @ipy.check(pl_utils.has_linked_realm)
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
                embed = utils.make_embed(result)
                if event:
                    await event.ctx.send(
                        embeds=embed,
                        ephemeral=True,
                    )
                await ctx.edit(msg, embeds=embed, components=[])  # type: ignore

        else:
            config.warning_notifications = True
            await config.save()

            await ctx.send(embeds=utils.make_embed("Enabled the warnings."))

    @config.subcommand(
        sub_cmd_name="realm-offline-role",
        sub_cmd_description=(
            "Sets (or unsets) the role that should be pinged in the autorunner channel"
            " if the Realm goes offline."
        ),
    )
    @ipy.check(pl_utils.has_linked_realm)
    async def set_realm_offline_role(
        self,
        ctx: utils.RealmContext,
        role: typing.Optional[ipy.Role] = tansy.Option("The role to ping."),
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
                role: ipy.Role = await self.bot.cache.fetch_role(ctx.guild_id, role)

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
                embed = utils.make_embed(result)
                if event:
                    await event.ctx.send(
                        embeds=embed,
                        ephemeral=True,
                    )
                await ctx.edit(msg, embeds=embed, components=[])  # type: ignore
        else:
            if not config.realm_offline_role:
                raise utils.CustomCheckFailure(
                    "There was no role set in the first place."
                )

            config.realm_offline_role = None
            await config.save()
            await ctx.send(embeds=utils.make_embed("Unset the Realm offline ping."))

    @config.subcommand(
        sub_cmd_name="help",
        sub_cmd_description="Tells you how to set up this bot.",
    )
    async def setup_help(
        self,
        ctx: utils.RealmContext,
    ) -> None:
        embed = utils.make_embed(
            "To set up this bot, follow the Server Setup Guide below.",
            title="Setup Bot",
        )
        button = ipy.Button(
            style=ipy.ButtonStyle.LINK,
            label="Server Setup Guide",
            url=os.environ["SETUP_LINK"],
        )
        await ctx.send(embeds=embed, components=button)

    watchlist = tansy.SlashCommand(
        name="watchlist",
        description=(
            "A series of commands to manage people to watch over and send messages if"
            " they join."
        ),
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )
    watchlist.add_check(pl_utils.has_linked_realm)

    @watchlist.subcommand(
        sub_cmd_name="list",
        sub_cmd_description=(
            "Sends a list of people on this server's watchlist and the role pinged when"
            " one joins (if set)."
        ),
    )
    async def watchlist_list(self, ctx: utils.RealmContext) -> None:
        config = await ctx.fetch_config()

        if config.player_watchlist:
            gamertags = await pl_utils.get_xuid_to_gamertag_map(
                self.bot, config.player_watchlist
            )
            watchlist = "\n".join(
                f"`{gamertags[xuid] or f'Player with XUID {xuid}'}`"
                for xuid in config.player_watchlist
            )
        else:
            watchlist = "N/A"

        desc = f"**Role:** N/A (use {self.watchlist_ping_role.mention()} to set)\n"
        if config.player_watchlist_role:
            desc = f"**Role**: <@&{config.player_watchlist_role}>\n"
        desc += f"**Watchlist**:\n{watchlist}"

        desc += (
            f"\n\n*Use {self.watchlist_add.mention()} and"
            f" {self.watchlist_remove.mention()} to add or remove people to/from the"
            " watchlist. A maximum of 3 people can be on the list.*"
        )
        await ctx.send(embed=utils.make_embed(desc, title="Player Watchlist"))

    @watchlist.subcommand(
        sub_cmd_name="add",
        sub_cmd_description=(
            "Adds a player to the watchlist, sending a message when they"
            " join. Maximum of 3 people."
        ),
    )
    @ipy.check(pl_utils.has_playerlist_channel)
    async def watchlist_add(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the user to watch for."),
    ) -> None:
        xuid = await pl_utils.xuid_from_gamertag(self.bot, gamertag)
        config = await ctx.fetch_config()

        if len(config.player_watchlist) >= 3:
            raise utils.CustomCheckFailure(
                "You can only track up to three players at once."
            )

        if xuid in config.player_watchlist:
            raise ipy.errors.BadArgument("This user is already in your watchlist.")

        config.player_watchlist.append(xuid)
        self.bot.player_watchlist_store[f"{config.realm_id}-{xuid}"].add(
            config.guild_id
        )
        await config.save()

        await ctx.send(
            embeds=utils.make_embed(f"Added `{gamertag}` to the player watchlist.")
        )

    @watchlist.subcommand(
        sub_cmd_name="remove",
        sub_cmd_description="Removes a player from the watchlist.",
    )
    async def watchlist_remove(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option(
            "The gamertag of the user to remove from the list."
        ),
    ) -> None:
        xuid = await pl_utils.xuid_from_gamertag(self.bot, gamertag)

        config = await ctx.fetch_config()

        if not config.player_watchlist:
            raise ipy.errors.BadArgument("This user is not in your watchlist.")

        try:
            config.player_watchlist.remove(xuid)
            await config.save()
        except ValueError:
            raise ipy.errors.BadArgument(
                "This user is not in your watchlist."
            ) from None

        self.bot.player_watchlist_store[f"{config.realm_id}-{xuid}"].discard(
            config.guild_id
        )

        await ctx.send(
            embeds=utils.make_embed(f"Removed `{gamertag}` from the player watchlist.")
        )

    @watchlist.subcommand(
        sub_cmd_name="ping-role",
        sub_cmd_description=(
            "Sets or unsets the role to be pinged when a player on the watchlist joins"
            " the linked Realm."
        ),
    )
    @ipy.check(pl_utils.has_playerlist_channel)
    async def watchlist_ping_role(
        self,
        ctx: utils.RealmContext,
        role: typing.Optional[ipy.Role] = tansy.Option("The role to ping."),
        unset: bool = tansy.Option("Should the role be unset?", default=False),
    ) -> None:
        if not (unset ^ bool(role)):
            raise ipy.errors.BadArgument(
                "You must either set a role or explictly unset the role. One must be"
                " given."
            )

        config = await ctx.fetch_config()

        if role:
            if isinstance(role, str):  # ???
                role: ipy.Role = await self.bot.cache.fetch_role(ctx.guild_id, role)

            if (
                not role.mentionable
                and ipy.Permissions.MENTION_EVERYONE not in ctx.app_permissions
            ):
                raise utils.CustomCheckFailure(
                    "I cannot ping this role. Make sure the role is either mentionable"
                    " or the bot can mention all roles."
                )

            config.player_watchlist_role = int(role.id)
            await config.save()
            await ctx.send(
                embed=utils.make_embed(
                    f"Set the player watchlist role to {role.mention}."
                )
            )

        else:
            config.player_watchlist_role = None
            await config.save()
            await ctx.send(
                embed=utils.make_embed(
                    "Unset the player watchlist role. This does not turn of the player"
                    " watchlist - please remove all players from the watchlist to do"
                    " that."
                )
            )


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(device_code)
    importlib.reload(clubs_playerlist)
    importlib.reload(cclasses)
    GuildConfig(bot)
