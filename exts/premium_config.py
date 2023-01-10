import asyncio
import importlib
import os
import secrets
import typing

import naff
import tansy
from Crypto.Cipher import AES

import common.models as models
import common.utils as utils


class PremiumHandling(naff.Extension):
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
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    async def generate_code(
        self,
        ctx: naff.InteractionContext,
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
        name="premium",  # type: ignore
        description="Handles the configuration for Realms Playerlist Premium.",  # type: ignore
        default_member_permissions=naff.Permissions.MANAGE_GUILD,
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
            raise naff.errors.BadArgument(
                f'Invalid code: "{code}". Are you sure this is the correct code and'
                " that you typed it in correctly?"
            )

        if code_obj.user_id and ctx.author.id != code_obj.user_id:
            raise naff.errors.BadArgument(
                f'Invalid code: "{code}". Are you sure this is the correct code and'
                " that you typed it in correctly?"
            )

        if code_obj.max_uses == code_obj.uses:
            raise naff.errors.BadArgument("This code cannot be redeemed anymore.")

        config = await ctx.fetch_config()

        if config.premium_code and config.premium_code.code == code:
            raise naff.errors.BadArgument("This code has already been redeem here.")

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
        sub_cmd_name="toggle-live-playerlist",
        sub_cmd_description=(
            "Toggles the live playerlist. Can only be run for servers with"
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
