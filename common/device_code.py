import asyncio
import datetime
import os

import elytra
import interactions as ipy
import orjson

import common.utils as utils


async def handle_flow(
    ctx: utils.RealmContext, msg: ipy.Message
) -> elytra.OAuth2TokenResponse:
    async with ctx.bot.session.get(
        "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode",
        data={
            "client_id": os.environ["XBOX_CLIENT_ID"],
            "scope": "Xboxlive.signin",
        },
    ) as resp:
        resp.raise_for_status()
        init_data = await resp.json(loads=orjson.loads)

    success_response: elytra.OAuth2TokenResponse | None = None

    await ctx.edit(
        msg,
        embeds=utils.make_embed(
            f"Please go to {init_data['verification_uri']} and enter code"
            f" `{init_data['user_code']}` to authenticate. The bot will periodically"
            " check to see if/when the account is authenticated.\n\n*You have 5"
            " minutes to authenticate.*"
        ),
        components=[],
    )

    try:
        async with asyncio.timeout(300):
            while True:
                await asyncio.sleep(init_data["interval"])

                async with ctx.bot.session.post(
                    "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                    data={
                        "client_id": os.environ["XBOX_CLIENT_ID"],
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        "device_code": init_data["device_code"],
                    },
                ) as resp:
                    resp_json = await resp.json()
                    if error := resp_json.get("error"):
                        if error in {
                            "authorization_declined",
                            "expired_token",
                            "bad_verification_code",
                        }:
                            break
                    else:
                        resp_json.pop("ext_expires_in", None)
                        resp_json["user_id"] = ""

                        if not resp_json.get("refresh_token"):
                            resp_json["refresh_token"] = ""

                        success_response = elytra.OAuth2TokenResponse(**resp_json)
                        break
    except asyncio.TimeoutError:
        raise utils.CustomCheckFailure("Authentication timed out.") from None

    if success_response is None:
        raise utils.CustomCheckFailure("Authentication failed or was cancelled.")

    return success_response


async def handle_realms(
    ctx: utils.RealmContext, msg: ipy.Message, oauth: elytra.OAuth2TokenResponse
) -> elytra.FullRealm:
    await ctx.edit(msg, embeds=utils.make_embed("Getting Realms data..."))

    user_xbox = await elytra.XboxAPI.from_oauth(
        os.environ["XBOX_CLIENT_ID"], os.environ["XBOX_CLIENT_SECRET"], oauth
    )
    user_xuid = user_xbox.auth_mgr.xsts_token.xuid  # yes, that's all i need
    await user_xbox.close()

    user_realms = await elytra.BedrockRealmsAPI.from_oauth(
        os.environ["XBOX_CLIENT_ID"], os.environ["XBOX_CLIENT_SECRET"], oauth
    )
    realms = await user_realms.fetch_realms()
    owned_realms = [
        r for r in realms.servers if r.owner_uuid == user_xuid and not r.expired
    ]

    try:
        if not owned_realms:
            raise utils.CustomCheckFailure(
                "You do not own any active Realms. Please create one and try again."
            )

        select_realm = ipy.StringSelectMenu(
            *(
                ipy.StringSelectOption(label=r.name, value=str(r.id))
                for r in owned_realms
            ),
            placeholder="Select a Realm",
        )
        await ctx.edit(
            msg,
            embeds=utils.make_embed(
                "Select a Realm to add the bot to:\n*You have 5 minutes to complete"
                " this.*"
            ),
            components=[select_realm],
        )

        try:
            event = await ctx.bot.wait_for_component(msg, select_realm, timeout=300)
            await event.ctx.defer(edit_origin=True)
            await ctx.edit(
                msg, embeds=utils.make_embed("Adding bot to Realm..."), components=[]
            )
        except asyncio.TimeoutError:
            await ctx.edit(msg, components=[])
            raise utils.CustomCheckFailure("Realm selection timed out.") from None

        realm_id = int(event.ctx.values[0])
        associated_realm = next((r for r in realms.servers if r.id == realm_id), None)
        if associated_realm is None:
            raise utils.CustomCheckFailure(
                "The Realm you selected no longer exists. Please try again."
            )

        await user_realms.invite_player(realm_id, ctx.bot.xbox.auth_mgr.xsts_token.xuid)
        await asyncio.sleep(5)

        block_off_time = int(
            (
                datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=2)
            ).timestamp()
        )
        pending_invites = await ctx.bot.realms.fetch_pending_invites()

        # yeah, not the best, but we'll make it work
        invite = next(
            (
                i
                for i in pending_invites.invites
                if i.world_owner_uuid == user_xuid
                and i.world_name == associated_realm.name
                and i.date_timestamp >= block_off_time
            ),
            None,
        )
        if invite is None:
            raise utils.CustomCheckFailure(
                "Failed to send invite to Realm. Please try again."
            )

        await ctx.bot.realms.accept_invite(invite.invitation_id)
        return associated_realm
    finally:
        await user_realms.close()
