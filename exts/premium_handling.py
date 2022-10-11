import importlib
import os
import secrets

import naff

import common.models as models
import common.utils as utils


class PremiumHandling(naff.Extension):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.name = "Premium Handling"

    @naff.slash_command(
        name="generate-code",
        description="Generates a premium code. Can only be used by the bot's owner.",
        scopes=[utils.DEV_GUILD_ID],
        default_member_permissions=naff.Permissions.ADMINISTRATOR,
    )
    @naff.slash_option(
        "max_uses",
        "How many uses the code has.",
        naff.OptionTypes.INTEGER,
        required=False,
    )
    @naff.slash_option(
        "user_id",
        "The user ID this is tied to if needed.",
        naff.OptionTypes.STRING,
        required=False,
    )
    async def generate_code(
        self, ctx: naff.InteractionContext, max_uses: int = 3, user_id: str = None
    ):
        # mind you, it isn't TOO important that this is secure - really, i just want
        # to make sure your average tech person couldn't brute force a code
        actual_user_id = int(user_id) if user_id is not None else None
        code = secrets.token_urlsafe(32)
        await models.PremiumCode.create(
            code=code, user_id=actual_user_id, max_uses=max_uses
        )
        await ctx.send(f"Code created!\nCode: `{code}`")

    premium = naff.SlashCommand(
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
    @naff.slash_option(
        "code",
        "The code for premium.",
        naff.OptionTypes.STRING,
        required=True,
    )
    async def redeem_premium(self, ctx: utils.RealmContext, code: str):
        code_obj = await models.PremiumCode.get_or_none(code=code)

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
        sub_cmd_name="info",
        sub_cmd_description=(
            "Gives you information about Realms Playerlist Premium and how to get it."
        ),
    )
    async def premium_info(self, ctx: utils.RealmContext):
        await ctx.send(os.environ["PREMIUM_INFO_LINK"])


def setup(bot):
    importlib.reload(utils)
    PremiumHandling(bot)
