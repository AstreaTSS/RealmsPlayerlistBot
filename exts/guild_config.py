"""
Copyright 2020-2024 AstreaTSS.
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
import importlib
import logging
import os
import re
import secrets
import typing

import elytra
import httpx
import interactions as ipy
import tansy

import common.classes as cclasses
import common.device_code as device_code
import common.models as models
import common.playerlist_utils as pl_utils
import common.premium_utils as premium_utils
import common.realm_stories as realm_stories
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


class SecurityCheckResults(typing.NamedTuple):
    user_xuid: str
    msg: ipy.Message
    microsoft_link: bool = False


logger = logging.getLogger("realms_bot")


class GuildConfig(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.name = "Server Config"
        self.bot: utils.RealmBotBase = bot

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

        if not config.premium_code and (
            config.live_playerlist or config.fetch_devices or config.live_online_channel
        ):
            await pl_utils.invalidate_premium(self.bot, config)

        embed = await utils.config_info_generate(
            ctx, config, diagnostic_info=diagnostic_info
        )
        await ctx.send(embeds=embed)

    async def add_realm(
        self,
        ctx: utils.RealmContext | utils.RealmModalContext,
        realm: elytra.FullRealm,
        *,
        microsoft_link: bool = False,
    ) -> list[ipy.Embed]:
        config = await ctx.fetch_config()

        config.realm_id = str(realm.id)

        # you may think this is weird, but if a realm is actually offline when it's
        # linked, the bot has no way of ever figuring that out, and so the bot will
        # never warn about the realm at all
        # if it is online though, it'll quickly be removed from the set, so this works
        # out well enough
        self.bot.offline_realms.add(realm.id)

        embeds: list[ipy.Embed] = []

        if not await models.PlayerSession.prisma().count(
            where={"realm_id": str(realm.id)}
        ):
            result = await realm_stories.fill_in_data_from_stories(
                self.bot, config.realm_id
            )

            if not result:
                warning_embed = ipy.Embed(
                    title="Warning",
                    description=(
                        "I was unable to backfill player data for this Realm. If"
                        f" you use {self.bot.mention_command('playerlist')}, it may"
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
                f" `{utils.FORMAT_CODE_REGEX.sub('', realm.name)}`\n\n**IMPORTANT"
                " NOTE:** There will now be an account called"
                f" `{self.bot.own_gamertag}` on your Realm's player roster (and even"
                " the playerlist). *Do not ban or kick them.* The bot will not work"
                " with your Realm if you do so."
            ),
            color=ipy.RoleColors.GREEN,
        )
        if microsoft_link:
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

    async def remove_realm(
        self, ctx: utils.RealmContext | utils.RealmModalContext
    ) -> None:
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
                if e.resp.status_code in {403, 404}:
                    logger.warning("Could not leave Realm with ID %s.", realm_id)
                else:
                    raise

            await models.PlayerSession.prisma().delete_many(
                where={"realm_id": realm_id}
            )

            self.bot.offline_realms.discard(int(realm_id))
            self.bot.dropped_offline_realms.discard(int(realm_id))
            await self.bot.redis.delete(
                f"missing-realm-{realm_id}", f"invalid-realmoffline-{realm_id}"
            )

    async def security_check(
        self, ctx: utils.RealmModalContext
    ) -> SecurityCheckResults | None:
        embed = ipy.Embed(
            title="Security Check",
            description=(
                "You must verify that you are an operator/moderator of the Realm you"
                " wish to link. There are two methods to do this:\n- *Temporarily* link"
                " your Xbox/Microsoft account so that the bot can verify who you are."
                " This is the recommended method, as it is the most secure -"
                " furthermore, the bot will not store your credentials.\n- Send a"
                " specific message to the bot's Xbox/Microsoft account. This method is"
                " less secure.\n\n**Please pick the method you wish to use. You have 2"
                " minutes to do so.**"
            ),
            timestamp=ipy.Timestamp.utcnow(),
            color=ipy.RoleColors.YELLOW,
        )

        success = False
        result = ""
        event: typing.Optional[ipy.events.Component] = None

        components = [
            ipy.Button(
                style=ipy.ButtonStyle.BLURPLE,
                label="Link Xbox/Microsoft account",
                emoji=f"<:xbox_one:{os.environ['XBOX_ONE_EMOJI_ID']}>",
            ),
            ipy.Button(
                style=ipy.ButtonStyle.BLURPLE,
                label="DM the bot's Xbox/Microsoft account",
                emoji="📥",
            ),
            ipy.Button(
                style=ipy.ButtonStyle.RED, label="I'm not an operator", emoji="✖️"
            ),
        ]
        msg = await ctx.send(embed=embed, components=components, ephemeral=True)

        try:
            event = await self.bot.wait_for_component(
                msg, components, self.button_check(ctx.author.id), timeout=120
            )

            if event.ctx.custom_id == components[-1].custom_id:
                result = "Unforunately, you must be an operator to link a Realm."
                ipy.get_logger().info(
                    "User %s declined the security check.", ctx.author.id
                )
            else:
                result = "Loading..."
                success = True
        except TimeoutError:
            result = "Timed out."
        finally:
            if event:
                await event.ctx.defer(edit_origin=True)

            if success:
                embed = utils.make_embed(result)
            else:
                embed = utils.error_embed_generate(result)

            await ctx.edit(msg, embeds=embed, components=[])

        if not success or not event:
            return None

        if event.ctx.custom_id == components[0].custom_id:
            ipy.get_logger().info(
                "User %s chose to link their account for the security check.",
                ctx.author.id,
            )

            oauth = await device_code.handle_flow(ctx, msg)
            user_xbox = await elytra.XboxAPI.from_oauth(
                os.environ["XBOX_CLIENT_ID"], os.environ["XBOX_CLIENT_SECRET"], oauth
            )
            return SecurityCheckResults(user_xbox.auth_mgr.xsts_token.xuid, msg, True)

        ipy.get_logger().info(
            "User %s chose to send a message for the security check.", ctx.author.id
        )

        verification_code = ""
        while not verification_code or premium_utils.has_bad_word(verification_code):
            verification_code = "".join(
                secrets.choice(premium_utils.SYMBOLS) for _ in range(6)
            )

        embed = utils.make_embed(
            "Please send the following message to the bot's Xbox/Microsoft account at"
            f" `{self.bot.own_gamertag}`. You can use either an Xbox console or the"
            f" Xbox app on PC/mobile to do so.\n\n`{verification_code}`\n\nOnce you"
            " have done so, click the button below to verify that you have sent the"
            " message. You have 10 minutes to do so.",
        )

        button = ipy.Button(
            style=ipy.ButtonStyle.GREEN,
            label="Verify Message",
            emoji="✅",
        )
        await ctx.edit(msg, embeds=embed, components=[button])
        button_disabled = ipy.Button.from_dict(button.to_dict())
        button_disabled.disabled = True

        try:
            async with asyncio.timeout(600):
                while True:
                    event = await self.bot.wait_for_component(
                        msg, button, self.button_check(ctx.author.id)
                    )
                    await event.ctx.defer(edit_origin=True)
                    await event.ctx.edit(
                        embeds=utils.make_embed("Verifying message..."),
                        components=[button_disabled],
                    )

                    conversation: elytra.Conversation | None = None

                    for folder_type in ("Secondary", "Primary"):
                        folder = await self.bot.xbox.fetch_folder(folder_type, 50)

                        if not folder.conversations:
                            continue

                        conversation = next(
                            (
                                c
                                for c in folder.conversations
                                if c.last_message.content_payload
                                and verification_code
                                in c.last_message.content_payload.full_content.upper()
                            ),
                            None,
                        )
                        if conversation:
                            break

                    if not conversation:
                        await ctx.send(
                            embed=utils.error_embed_generate("Could not find message."),
                            ephemeral=True,
                        )
                        await event.ctx.edit(embeds=embed, components=[button])
                        continue

                    await self.bot.xbox.delete_conversation(
                        conversation.conversation_id,
                        conversation.last_message.message_id,
                    )
                    return SecurityCheckResults(conversation.last_message.sender, msg)

        except TimeoutError:
            await ctx.edit(
                msg, embed=utils.error_embed_generate("Timed out."), components=[]
            )
            return None

    @config.subcommand(
        sub_cmd_name="link-realm",
        sub_cmd_description="Links (or unlinks) a Realm to this server.",
    )
    @ipy.auto_defer(enabled=False)
    async def link_realm(
        self,
        ctx: utils.RealmContext,
        link_method: int = tansy.Option(
            "The method for linking/unlinking.",
            choices=[
                ipy.SlashCommandChoice("Realm Code/Link (Requires Being Operator)", 1),
                ipy.SlashCommandChoice("Direct Link (Requires Being Owner)", 2),
                ipy.SlashCommandChoice("Unlink", -1),
            ],
        ),
    ) -> None:
        if link_method == -1:
            await ctx.defer()
            await self.remove_realm(ctx)
            await ctx.send(embeds=utils.make_embed("Unlinked the Realm."))
            return

        if link_method == 1:
            modal = ipy.Modal(
                ipy.InputText(
                    label="What's your Realm code/link?",
                    style=ipy.TextStyles.SHORT,
                    custom_id="realm_code",
                    min_length=3,
                ),
                title="Realm Code/Link Entry",
                custom_id="realm_code_modal",
            )
            await ctx.send_modal(modal)
            return

        if link_method == 2:
            await ctx.defer(ephemeral=True)
            msg = await ctx.send(embeds=utils.make_embed("Loading..."))

            config = await ctx.fetch_config()

            try:
                oauth = await device_code.handle_flow(ctx, msg)
                realm = await device_code.handle_realms(ctx, msg, oauth)
            except ipy.errors.HTTPException as e:
                if e.status == 404:
                    # probably just cant edit embed because it was dismissed
                    return
                raise

            if config.realm_id and config.realm_id != str(realm.id):
                await self.remove_realm(ctx)

            embeds = await self.add_realm(ctx, realm, microsoft_link=True)
            await ctx.edit(msg, embeds=embeds, components=[])
            return

        raise ipy.errors.BadArgument("Invalid link method.")

    @ipy.modal_callback("realm_code_modal")
    async def _realm_code_modal(self, ctx: utils.RealmModalContext) -> None:
        await ctx.defer(ephemeral=True)
        config = await ctx.fetch_config()

        _realm_code = ctx.responses["realm_code"]

        if not _realm_code:
            raise utils.CustomCheckFailure("No Realm code/link provided.")

        realm_code_matches = REALMS_LINK_REGEX.fullmatch(_realm_code)

        if not realm_code_matches:
            raise ipy.errors.BadArgument("Invalid Realm code!")

        realm_code = realm_code_matches[1]

        results: SecurityCheckResults | None = None

        try:
            realm = await ctx.bot.realms.fetch_realm_from_code(realm_code)

            if utils.FEATURE("SECURITY_CHECK"):
                await ctx.bot.redis.set(
                    f"rpl-security-check-{ctx.author.id}", "1", ex=3600
                )
                ipy.get_logger().info("Running security check for %s.", ctx.author.id)
                results = await self.security_check(ctx)
                if not results:
                    return

            # needed otherwise the next fetch realm won't work
            realm = await ctx.bot.realms.join_realm_from_code(realm_code)

            if results and realm.owner_uuid != results.user_xuid:
                usable_realm = await ctx.bot.realms.fetch_realm(realm.id)

                try:
                    if not usable_realm.players:
                        raise ipy.errors.BadArgument(
                            "I could not verify that you are an operator of this Realm."
                        )

                    player_info = next(
                        (
                            p
                            for p in usable_realm.players
                            if p.uuid == results.user_xuid
                        ),
                        None,
                    )

                    if not player_info:
                        raise ipy.errors.BadArgument(
                            "You are not an operator of this Realm."
                        )

                    if player_info.permission != elytra.Permission.OPERATOR:
                        raise ipy.errors.BadArgument(
                            "You are not an operator of this Realm."
                        )
                except ipy.errors.BadArgument as e:
                    if not await models.GuildConfig.prisma().count(
                        where={"realm_id": str(realm.id)}
                    ) and utils.FEATURE("HANDLE_MISSING_REALMS"):
                        try:
                            await ctx.bot.realms.leave_realm(realm.id)
                        except elytra.MicrosoftAPIException as e:
                            if e.resp.status_code in {403, 404}:
                                logger.warning(
                                    "Could not leave Realm with ID %s.", realm.id
                                )
                            else:
                                raise

                    await ctx.edit(
                        results.msg,
                        embeds=utils.error_embed_generate(str(e)),
                        components=[],
                    )
                    return

            if config.realm_id and config.realm_id != str(realm.id):
                await self.remove_realm(ctx)

            embeds = await self.add_realm(
                ctx,
                realm,
                microsoft_link=results is not None and results.microsoft_link,
            )

            if results:
                await ctx.edit(results.msg, embeds=embeds, components=[])
            else:
                await ctx.send(embeds=embeds)
        except elytra.MicrosoftAPIException as e:
            if not isinstance(
                e.error, httpx.HTTPStatusError
            ) or e.resp.status_code not in {
                403,
                404,
            }:
                raise

            error_msg = (
                "I cannot link this Realm. Please make sure the Realm code"
                " is spelled correctly, and that the code is valid. Also, make"
                " sure that you have not banned or kicked"
                f" `{self.bot.own_gamertag}` from the Realm."
            )

            if results:
                await ctx.edit(
                    results.msg,
                    embeds=utils.error_embed_generate(error_msg),
                    components=[],
                )
                return

            raise ipy.errors.BadArgument(error_msg) from None

    @config.subcommand(
        sub_cmd_name="autorunning-playerlist-channel",
        sub_cmd_description=(
            "Sets (or unsets) where the autorunning playerlist is sent to."
        ),
    )
    @ipy.check(pl_utils.has_linked_realm)
    async def set_autorunning_playerlist_channel(
        self,
        ctx: utils.RealmContext,
        channel: typing.Optional[ipy.GuildText] = tansy.Option(
            "The channel to set the autorunning playerlist to.",
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
                assert isinstance(channel, ipy.GuildText)

            config.playerlist_chan = channel.id
            await config.save()
            await self.bot.redis.delete(
                f"invalid-playerlist3-{config.guild_id}",
                f"invalid-playerlist7-{config.guild_id}",
            )

            await ctx.send(
                embeds=utils.make_embed(
                    f"Set the autorunning playerlist channel to {channel.mention}."
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

            await ctx.send(
                embeds=utils.make_embed("Unset the autorunning playerlist channel.")
            )

    @staticmethod
    def button_check(author_id: int) -> typing.Callable[..., bool]:
        def _check(event: ipy.events.Component) -> bool:
            return event.ctx.author.id == author_id

        return _check

    @config.subcommand(
        sub_cmd_name="realm-warning",
        sub_cmd_description=(
            "Toggles the sending of warnings after detecting inactivity in the Realm."
        ),
    )
    @ipy.check(pl_utils.has_linked_realm)
    async def toggle_realm_warnings(
        self,
        ctx: utils.RealmContext,
        toggle: bool = tansy.Option("Should the warning be sent?"),
    ) -> None:
        """
        Toggles the sending of warnings after detecting inactivity in the Realm.
        This warning is usually sent after 24 hours of no activity has been detected.
        This is usually beneficial, but may be annoying if you have a Realm that is rarely used.

        Do note that the Realm will still be unlinked after 7 days of inactivity, regardless of this.
        """

        config = await ctx.fetch_config()

        if config.warning_notifications == toggle:
            raise ipy.errors.BadArgument("That's already the current setting.")

        if not toggle:
            embed = ipy.Embed(
                title="⚠ Warning ⚠",
                description=(
                    "This warning is usually a very important warning. If the bot"
                    " cannot find any players on the Realm after 24 hours, this"
                    " usually means that either the Realm is down, and so the"
                    " playerlist should be turned off, or that"
                    f" `{self.bot.own_gamertag}` has been kicked/banned, preventing the"
                    " bot from functioning. **You should not disable this warning"
                    " lightly, as it could be critical to fixing issues with the"
                    " bot.**\n**Also note that the Realm's autorunners and related"
                    " settings will still be disabled after 7 days of inactivity. It"
                    " is your responsibility to keep track of this.**\nDisabling these"
                    " warnings may still be beneficial if your Realm isn't as active,"
                    " though, as long as you are aware of the risks.\n\n**If you wish"
                    " to continue to silence these warnings, press the accept"
                    " button.** You have two minutes to do so."
                ),
                timestamp=ipy.Timestamp.utcnow(),
                color=ipy.RoleColors.ORANGE,  # please pay attention to this warning
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
            except TimeoutError:
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
            "Sets/unsets the role that is pinged in the autorunning playerlist channel"
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
        Sets/unsets the role that is pinged in the autorunning playerlist channel if the Realm goes offline.
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
                    "Please set up the autorunning playerlist with"
                    f" {self.set_autorunning_playerlist_channel.mention()} first."
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
            except TimeoutError:
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
        sub_cmd_name="notification-channel",
        sub_cmd_description=(
            "Sets/reset the channels used for notifications from the bot. Defaults to"
            " the playerlist channel."
        ),
    )
    @ipy.check(pl_utils.has_linked_realm)
    async def set_notification_channel(
        self,
        ctx: utils.RealmContext,
        feature: typing.Literal[
            "player_watchlist", "realm_offline", "reoccurring_leaderboard"
        ] = tansy.Option(
            "The feature/notification type to set the channel for.",
            choices=[
                ipy.SlashCommandChoice("Player Watchlist", "player_watchlist"),
                ipy.SlashCommandChoice("Realm Offline Notifications", "realm_offline"),
                ipy.SlashCommandChoice(
                    "Reoccurring Leaderboard", "reoccurring_leaderboard"
                ),
            ],
            type=str,
        ),
        channel: typing.Optional[ipy.GuildText] = tansy.Option(
            "The channel to set the feature to.",
            converter=cclasses.ValidChannelConverter,
        ),
        reset: bool = tansy.Option(
            "Should the channel be reset? If so, the playerlist channel will be"
            " used instead.",
            default=False,
        ),
    ) -> None:
        if not (reset ^ bool(channel)):
            raise ipy.errors.BadArgument(
                "You must either set a channel or explictly reset the channel. One must"
                " be given."
            )

        config = await ctx.fetch_config()

        if channel is not None:
            config.notification_channels[feature] = channel.id
            await config.save()

            await ctx.send(
                embeds=utils.make_embed(f"Set the channel to {channel.mention}.")
            )
        else:
            result = config.notification_channels.pop(feature, None)
            if result is None:
                raise ipy.errors.BadArgument(
                    "There was no channel set in the first place."
                )
            await config.save()

            await ctx.send(
                embeds=utils.make_embed(
                    "Reset the channel. The playerlist channel will be used for that"
                    " type of notification instead."
                )
            )

    @config.subcommand(
        sub_cmd_name="help",
        sub_cmd_description=(
            "Tells you how to set up this bot and gives an overview of its features."
        ),
    )
    async def setup_help(
        self,
        ctx: utils.RealmContext,
    ) -> None:
        embed = utils.make_embed(
            "To set up this bot, follow the Server Setup Guide below. You can also"
            " check out the various features of the bot through the other button.",
            title="Configuration Help",
        )
        components = [
            ipy.Button(
                style=ipy.ButtonStyle.LINK,
                label="Server Setup Guide",
                url="https://rpl.astrea.cc/wiki/server_setup.html",
            ),
            ipy.Button(
                style=ipy.ButtonStyle.LINK,
                label="Bot Features",
                url="https://rpl.astrea.cc/wiki/features.html",
            ),
        ]
        await ctx.send(embeds=embed, components=components)

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
    @ipy.check(pl_utils.has_autorunning_playerlist_channel)
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
    @ipy.check(pl_utils.has_autorunning_playerlist_channel)
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

    @watchlist.subcommand(
        sub_cmd_name="channel",
        sub_cmd_description=(
            "Sets or resets the channel to send watchlist messages to. Defaults to the"
            " playerlist channel."
        ),
    )
    @ipy.check(pl_utils.has_linked_realm)
    async def watchlist_channel(
        self,
        ctx: utils.RealmContext,
        channel: typing.Optional[ipy.GuildText] = tansy.Option(
            "The channel to set the feature to.",
            converter=cclasses.ValidChannelConverter,
        ),
        reset: bool = tansy.Option(
            "Should the channel be reset? If so, the playerlist channel will be"
            " used instead.",
            default=False,
        ),
    ) -> None:
        await self.set_notification_channel.call_with_binding(
            self.set_notification_channel.callback,
            ctx,
            "player_watchlist",
            channel,
            reset,
        )

    nickname = tansy.SlashCommand(
        name="nickname",
        description="A series of commands to manage nicknames for users.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )
    nickname.add_check(pl_utils.has_linked_realm)

    @nickname.subcommand(
        sub_cmd_name="list",
        sub_cmd_description="Sends a list of nicknames set for this server.",
    )
    async def nicknames_list(self, ctx: utils.RealmContext) -> None:
        config = await ctx.fetch_config()

        if not config.nicknames:
            raise utils.CustomCheckFailure("This server has no nicknames set.")

        str_builder: list[str] = []
        gamertag_map = await pl_utils.get_xuid_to_gamertag_map(
            self.bot, list(config.nicknames.keys())
        )

        for xuid, nickname in config.nicknames.items():
            str_builder.append(f"`{gamertag_map[xuid] or xuid}` -> `{nickname}`")

        await ctx.send(
            embeds=utils.make_embed("\n".join(str_builder), title="Nickname List")
        )

    @nickname.subcommand(
        sub_cmd_name="set",
        sub_cmd_description="Sets a nickname for a given gamertag.",
    )
    async def nicknames_set(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the user."),
        nickname: str = tansy.Option("The new nickname for the user."),
    ) -> None:
        config = await ctx.fetch_config()

        if len(config.nicknames) >= 10:
            raise utils.CustomCheckFailure("Cannot set more than 10 nicknames.")

        xuid = await pl_utils.xuid_from_gamertag(self.bot, gamertag)
        config.nicknames[xuid] = nickname
        await config.save()

        await ctx.send(f"Nickname for `{gamertag}` set to `{nickname}`.")

    @nickname.subcommand(
        sub_cmd_name="remove",
        sub_cmd_description="Removes/unsets a nickname for a given gamertag.",
    )
    async def nicknames_remove(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the user."),
    ) -> None:
        config = await ctx.fetch_config()

        xuid = await pl_utils.xuid_from_gamertag(self.bot, gamertag)
        nickname = config.nicknames.pop(xuid, None)
        if not nickname:
            raise ipy.errors.BadArgument("This user didn't have a nickname to clear.")

        await config.save()

        await ctx.send(f"Removed nickname `{nickname}` for `{gamertag}`.")


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(device_code)
    importlib.reload(realm_stories)
    importlib.reload(cclasses)
    importlib.reload(pl_utils)
    importlib.reload(premium_utils)
    GuildConfig(bot)
