import importlib
import secrets
import typing

import naff

import common.models as models
import common.utils as utils


class PremiumHandling(naff.Extension):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot

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
        self, ctx: naff.InteractionContext, max_uses: int = 1, user_id: str = None
    ):
        # mind you, it isn't TOO important that this is secure - really, i just want
        # to make sure your average tech person couldn't brute force a code
        actual_user_id = int(user_id) if user_id is not None else None
        code = secrets.token_urlsafe()
        await models.PremiumCode.create(
            code=code, user_id=actual_user_id, max_uses=max_uses
        )
        await ctx.send(f"Code created!\nCode: `{code}`")

    @naff.slash_command(
        name="redeem-premium",
        description="Redeems the premium code for the server this command is run in.",
        default_member_permissions=naff.Permissions.MANAGE_GUILD,
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

        if config.premium_code == code:
            raise naff.errors.BadArgument("This code has already been redeem here.")

        config.premium_code = code_obj
        code_obj.uses += 1
        await config.save()
        await code_obj.save()

        remaining_uses = code_obj.max_uses - code_obj.uses
        uses_str = "uses" if remaining_uses != 1 else "use"

        await ctx.send(
            "Code redeemed for this server!\nThis code has"
            f" {remaining_uses} {uses_str}."
        )


def setup(bot):
    importlib.reload(utils)
    PremiumHandling(bot)