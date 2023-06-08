import asyncio
import importlib
import os
import secrets
import typing

import interactions as ipy
import tansy
from Crypto.Cipher import AES

import common.models as models
import common.utils as utils


class PremiumHandling(ipy.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.name = "Premium Handling"

    def _encrypt_input(self, code: str) -> str:
        key = bytes(os.environ["PREMIUM_ENCRYPTION_KEY"], "utf-8")
        # siv is best when we don't want nonces
        # we can't exactly use anything as a nonce since we have no way of obtaining
        # info about a code without the code itself - there's no username that a database
        # can look up to get the nonce
        aes = AES.new(key, AES.MODE_SIV)

        # the database stores values in keys - furthermore, only the first part of
        # the tuple given is actually the key
        return str(aes.encrypt_and_digest(bytes(code, "utf-8"))[0])  # type: ignore

    async def encrypt_input(self, code: str) -> str:
        # just because this is a technically complex function by design - aes isn't cheap
        return await asyncio.to_thread(self._encrypt_input, code)

    @tansy.slash_command(
        name="generate-code",
        description="Generates a premium code. Can only be used by the bot's owner.",
        scopes=[utils.DEV_GUILD_ID],
        default_member_permissions=ipy.Permissions.ADMINISTRATOR,
    )
    async def generate_code(
        self,
        ctx: ipy.InteractionContext,
        max_uses: int = tansy.Option("How many uses the code has.", default=3),
        user_id: typing.Optional[str] = tansy.Option(
            "The user ID this is tied to if needed.", default=None
        ),
    ) -> None:
        # mind you, it isn't TOO important that this is secure - really, i just want
        # to make sure your average tech person couldn't brute force a code
        # regardless, we do try to use aes here just in case

        actual_user_id = int(user_id) if user_id is not None else None

        code = secrets.token_urlsafe(16)
        encrypted_code = await self.encrypt_input(code)

        await models.PremiumCode.create(
            code=encrypted_code, user_id=actual_user_id, max_uses=max_uses
        )
        await ctx.send(f"Code created!\nCode: `{code}`")

    premium = tansy.TansySlashCommand(
        name="premium",
        description="Handles the configuration for Realms Playerlist Premium.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @premium.subcommand(
        sub_cmd_name="redeem",
        sub_cmd_description=(
            "Redeems the premium code for the server this command is run in."
        ),
    )
    async def redeem_premium(
        self, ctx: utils.RealmContext, code: str = tansy.Option("The code for premium.")
    ) -> None:
        encrypted_code = await self.encrypt_input(code)
        code_obj = await models.PremiumCode.get_or_none(code=encrypted_code)

        if not code_obj:
            raise ipy.errors.BadArgument(
                f'Invalid code: "{code}". Are you sure this is the correct code and'
                " that you typed it in correctly?"
            )

        if code_obj.user_id and ctx.author.id != code_obj.user_id:
            raise ipy.errors.BadArgument(
                f'Invalid code: "{code}". Are you sure this is the correct code and'
                " that you typed it in correctly?"
            )

        if code_obj.max_uses == code_obj.uses:
            raise ipy.errors.BadArgument("This code cannot be redeemed anymore.")

        config = await ctx.fetch_config()

        if config.premium_code and config.premium_code.code == code:
            raise ipy.errors.BadArgument("This code has already been redeem here.")

        config.premium_code = code_obj
        code_obj.uses += 1
        await config.save()
        await code_obj.save()

        remaining_uses = code_obj.max_uses - code_obj.uses
        uses_str = "uses" if remaining_uses != 1 else "use"

        await ctx.send(
            "Code redeemed for this server!\nThis code has"
            f" {remaining_uses} {uses_str} remaining."
        )

    @premium.subcommand(
        sub_cmd_name="live-playerlist",
        sub_cmd_description=(
            "Turns on or off the live playerlist. Can only be run for servers with"
            " premium activated."
        ),
    )
    async def toggle_live_playerlist(
        self,
        ctx: utils.RealmContext,
        toggle: bool = tansy.Option("Should it be on (true) or off (false)?"),
    ) -> None:
        config = await ctx.fetch_config()

        if not config.premium_code:
            raise utils.CustomCheckFailure(
                "This server does not have premium activated! Check out"
                f" {self.premium_info.mention()} for more information about it."
            )

        if not (config.realm_id and config.playerlist_chan):
            raise utils.CustomCheckFailure(
                "You need to link your Realm and set a playerlist channel before"
                " running this."
            )

        if toggle:
            self.bot.live_playerlist_store[config.realm_id].add(config.guild_id)
        else:
            self.bot.live_playerlist_store[config.realm_id].discard(config.guild_id)

        config.live_playerlist = toggle
        await config.save()
        await ctx.send(
            f"Turned {utils.toggle_friendly_str(toggle)} the live playerlist!"
        )

    @staticmethod
    def button_check(author_id: int) -> typing.Callable[..., bool]:
        def _check(event: ipy.events.Component) -> bool:
            return event.ctx.author.id == author_id

        return _check

    @premium.subcommand(
        sub_cmd_name="fetch-devices",
        sub_cmd_description=(
            "If enabled, fetches and displays devices of online players. Will make bot"
            " slower. Premium only."
        ),
    )
    async def toggle_fetch_devices(
        self,
        ctx: utils.RealmContext,
        toggle: bool = tansy.Option("Should it be on (true) or off (false)?"),
    ) -> None:
        config = await ctx.fetch_config()

        if not config.premium_code:
            raise utils.CustomCheckFailure(
                "This server does not have premium activated! Check out"
                f" {self.premium_info.mention()} for more information about it."
            )
        if not config.realm_id:
            raise utils.CustomCheckFailure(
                "You need to link your Realm before running this."
            )
        if config.fetch_devices == toggle:
            raise ipy.errors.BadArgument("That's already the current setting.")

        if toggle:
            embed = ipy.Embed(
                title="Warning",
                description=(
                    "This will fetch display the device the user is playing on if they"
                    " are on the Realm whenever the bot shows them.\n**However, this"
                    " will make the bot slower with certain commands**, like `/online`"
                    " and `/playerlist`, and also slow down the live playerlist"
                    " slightly (if enabled), as fetching the device requires a bit more"
                    " information that what is usually stored.\n\n**If you wish to"
                    " continue with enabling the fetching and displaying of devices,"
                    " press the accept button.** You have a minute to do so."
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
                    result = "Declined fetching and displaying devices."
                else:
                    config.fetch_devices = True
                    await config.save()
                    self.bot.fetch_devices_for.add(config.realm_id)

                    result = "Turned on fetching and displaying devices."
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
            config.fetch_devices = False
            await config.save()

            await ctx.send("Turned off fetching and displaying devices.")

            if not await models.GuildConfig.filter(
                realm_id=config.realm_id, fetch_devices=True
            ).exists():
                self.bot.fetch_devices_for.discard(config.realm_id)

    @premium.subcommand(
        sub_cmd_name="info",
        sub_cmd_description=(
            "Gives you information about Realms Playerlist Premium and how to get it."
        ),
    )
    async def premium_info(self, ctx: utils.RealmContext) -> None:
        await ctx.send(os.environ["PREMIUM_INFO_LINK"])


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    PremiumHandling(bot)
