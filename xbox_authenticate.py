import rpl_config

rpl_config.load()

import argparse
import asyncio
import os
from urllib.parse import urlencode

import aiohttp
import aiohttp.web
import aiohttp_retry
import msgspec

import common.microsoft_core as mscore

code: str | None = None


def generate_authorization_url(client_id: str, redirect_uri: str) -> str:
    """Generate Windows Live Authorization URL."""
    query_params = {
        "client_id": client_id,
        "response_type": "code",
        "approval_prompt": "auto",
        "scope": "Xboxlive.signin Xboxlive.offline_access",
        "redirect_uri": redirect_uri,
    }

    return f"https://login.live.com/oauth20_authorize.srf?{urlencode(query_params)}"


routes = aiohttp.web.RouteTableDef()


@routes.get("/auth/callback")
async def parse_response(req: aiohttp.web.Request) -> aiohttp.web.Response:
    global code

    try:
        if req.query.get("error"):
            return aiohttp.web.Response(
                text=f"Error: {req.query.get('error_description')}", status=400
            )

        if gotten_code := req.query.get("code"):
            code = gotten_code
            return aiohttp.web.Response(
                text="Success! You may now close this tab and go back to the terminal."
            )

        return aiohttp.web.Response(text="Error: No code was provided.", status=400)
    finally:
        app["event"].set()


app = aiohttp.web.Application()
app.add_routes(routes)


async def main() -> None:
    global code

    parser = argparse.ArgumentParser(
        description="Authenticate into Xbox and Realms API."
    )
    parser.add_argument(
        "--tokens",
        "-t",
        default="tokens.json",
        help="Token filepath. Default: 'tokens.json'",
    )
    parser.add_argument(
        "--client-id",
        "-cid",
        default=os.environ["XBOX_CLIENT_ID"],
        help="OAuth2 Client ID",
    )
    parser.add_argument(
        "--client-secret",
        default=os.environ["XBOX_CLIENT_SECRET"],
        help="OAuth2 Client Secret",
    )
    args = parser.parse_args()

    app["event"] = asyncio.Event()

    redirect_uri = "http://localhost:8080/auth/callback"

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "localhost", 8080)
    await site.start()

    print(  # noqa: T201
        f"Please visit {generate_authorization_url(args.client_id, redirect_uri)} to"
        " authenticate."
    )

    await app["event"].wait()
    await runner.cleanup()

    if code:
        auth_mgr = mscore.AuthenticationManager(
            aiohttp_retry.RetryClient(),
            args.client_id,
            args.client_secret,
            "http://xboxlive.com",
        )
        oauth = await auth_mgr.request_oauth_token(code, redirect_uri)
        with open(args.tokens, mode="wb") as f:
            f.write(msgspec.json.encode(oauth))

        await auth_mgr.close()
        print("Authentication successful!")  # noqa: T201
    else:
        print("Authentication failed.")  # noqa: T201


if __name__ == "__main__":
    asyncio.run(main())
