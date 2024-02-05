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
import datetime
import logging
import os

import elytra
import interactions as ipy
import orjson

import common.utils as utils

logger = logging.getLogger("realms_bot")


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
                        success_response = elytra.OAuth2TokenResponse.from_data(
                            resp_json
                        )
                        break
    except TimeoutError:
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
    user_xuid = user_xbox.auth_mgr.xsts_token.xuid
    my_xuid = ctx.bot.xbox.auth_mgr.xsts_token.xuid

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
                msg,
                embeds=utils.make_embed(
                    "Adding bot to Realm...\n*You may see the bot adding you as a"
                    " friend. This is part of the process - it'll unfriend you soon"
                    " after.*"
                ),
                components=[],
            )
        except TimeoutError:
            await ctx.edit(msg, components=[])
            raise utils.CustomCheckFailure("Realm selection timed out.") from None

        realm_id = int(event.ctx.values[0])
        associated_realm = next((r for r in realms.servers if r.id == realm_id), None)
        if associated_realm is None:
            raise utils.CustomCheckFailure(
                "The Realm you selected no longer exists. Please try again."
            )

        # work around potential mojang protections against inviting users to realms
        # note: not a bypass, the user has given permission to do this with oauth
        try:
            await user_xbox.add_friend(xuid=my_xuid)
            await ctx.bot.xbox.add_friend(xuid=user_xuid)
        except elytra.MicrosoftAPIException as e:
            # not too important, but we'll log it
            logger.warning("Failed to add %s as friend.", user_xuid, exc_info=e)

        await user_realms.invite_player(realm_id, my_xuid)
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

        try:
            await user_xbox.remove_friend(xuid=my_xuid)
            await ctx.bot.xbox.remove_friend(xuid=user_xuid)
        except elytra.MicrosoftAPIException as e:
            logger.warning("Failed to remove %s as friend.", user_xuid, exc_info=e)

        return associated_realm
    finally:
        await user_xbox.close()
        await user_realms.close()
