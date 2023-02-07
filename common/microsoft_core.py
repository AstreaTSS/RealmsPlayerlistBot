import asyncio
import os
import typing

import aiohttp
import apischema
import attrs
import orjson
from xbox.webapi.authentication.manager import AuthenticationManager
from xbox.webapi.authentication.models import (
    OAuth2TokenResponse,
    XAUResponse,
    XSTSResponse,
)

apischema.settings.additional_properties = True
apischema.settings.camel_case = True


# these methods are ripped out of xbox-webapi, but optimized for speed
# basically, im using orjson instead of the default json
async def _oauth2_token_request(
    auth_mgr: AuthenticationManager, data: dict
) -> OAuth2TokenResponse:
    """Execute token requests."""
    data["client_id"] = auth_mgr._client_id
    if auth_mgr._client_secret:
        data["client_secret"] = auth_mgr._client_secret
    resp = await auth_mgr.session.post(
        "https://login.live.com/oauth20_token.srf", data=data
    )
    resp.raise_for_status()
    return OAuth2TokenResponse.parse_obj(await resp.json(loads=orjson.loads))


async def refresh_oauth_token(auth_mgr: AuthenticationManager) -> OAuth2TokenResponse:
    """Refresh OAuth2 token."""
    return await _oauth2_token_request(
        auth_mgr,
        {
            "grant_type": "refresh_token",
            "scope": " ".join(auth_mgr._scopes),
            "refresh_token": auth_mgr.oauth.refresh_token,
        },
    )


async def request_user_token(
    auth_mgr: AuthenticationManager,
    relying_party: str = "http://auth.xboxlive.com",
    use_compact_ticket: bool = False,
) -> XAUResponse:
    """Authenticate via access token and receive user token."""
    url = "https://user.auth.xboxlive.com/user/authenticate"
    headers = {"x-xbl-contract-version": "1"}
    data = {
        "RelyingParty": relying_party,
        "TokenType": "JWT",
        "Properties": {
            "AuthMethod": "RPS",
            "SiteName": "user.auth.xboxlive.com",
            "RpsTicket": (
                auth_mgr.oauth.access_token
                if use_compact_ticket
                else f"d={auth_mgr.oauth.access_token}"
            ),
        },
    }

    resp = await auth_mgr.session.post(url, json=data, headers=headers)
    resp.raise_for_status()
    return XAUResponse.parse_obj(await resp.json(loads=orjson.loads))


async def request_xsts_token(
    auth_mgr: AuthenticationManager, relying_party: str = "http://xboxlive.com"
) -> XSTSResponse:
    """Authorize via user token and receive final X token."""
    url = "https://xsts.auth.xboxlive.com/xsts/authorize"
    headers = {"x-xbl-contract-version": "1"}
    data = {
        "RelyingParty": relying_party,
        "TokenType": "JWT",
        "Properties": {
            "UserTokens": [auth_mgr.user_token.token],
            "SandboxId": "RETAIL",
        },
    }

    resp = await auth_mgr.session.post(url, json=data, headers=headers)
    resp.raise_for_status()
    return XSTSResponse.parse_obj(await resp.json(loads=orjson.loads))


class MicrosoftAPIException(Exception):
    def __init__(self, resp: aiohttp.ClientResponse, error: Exception) -> None:
        self.resp = resp
        self.error = error

        super().__init__(
            "An error occured when trying to access this resource: code"
            f" {resp.status}.\nError: {error}"
        )


def _orjson_dumps_wrapper(obj: typing.Any) -> str:
    return orjson.dumps(obj).decode("utf-8")


@attrs.define()
class BaseMicrosoftAPI:
    relying_party: str = attrs.field(default="http://xboxlive.com")
    base_url: str = attrs.field(default="")
    set_up: asyncio.Event = attrs.field(init=False, factory=asyncio.Event)
    session: aiohttp.ClientSession = attrs.field(init=False)
    auth_mgr: AuthenticationManager = attrs.field(init=False)

    def __attrs_post_init__(self) -> None:
        self.session = aiohttp.ClientSession(json_serialize=_orjson_dumps_wrapper)

        self.auth_mgr = AuthenticationManager(
            self.session,
            os.environ["XBOX_CLIENT_ID"],
            os.environ["XBOX_CLIENT_SECRET"],
            "",
        )
        self.auth_mgr.oauth = OAuth2TokenResponse.parse_file(
            os.environ["XAPI_TOKENS_LOCATION"]
        )
        asyncio.create_task(self.refresh_tokens())

    @property
    def BASE_HEADERS(self) -> dict[str, str]:  # noqa: N802
        return {"Authorization": self.auth_mgr.xsts_token.authorization_header_value}

    async def close(self) -> None:
        await self.session.close()

    async def refresh_tokens(self, force_refresh: bool = False) -> None:
        """Refresh all tokens."""
        if force_refresh:
            self.auth_mgr.oauth = await refresh_oauth_token(self.auth_mgr)
            self.auth_mgr.user_token = await request_user_token(self.auth_mgr)
            self.auth_mgr.xsts_token = await request_xsts_token(
                self.auth_mgr,
                relying_party=self.relying_party,
            )
        else:
            if not (self.auth_mgr.oauth and self.auth_mgr.oauth.is_valid()):
                self.auth_mgr.oauth = await refresh_oauth_token(self.auth_mgr)
            if not (self.auth_mgr.user_token and self.auth_mgr.user_token.is_valid()):
                self.auth_mgr.user_token = await request_user_token(self.auth_mgr)
            if not (self.auth_mgr.xsts_token and self.auth_mgr.xsts_token.is_valid()):
                self.auth_mgr.xsts_token = await request_xsts_token(
                    self.auth_mgr,
                    relying_party=self.relying_party,
                )

        self.set_up.set()

    async def request(
        self,
        method: str,
        url: str,
        json: typing.Any = None,
        data: typing.Optional[dict] = None,
        params: typing.Optional[dict] = None,
        headers: typing.Optional[dict] = None,
        *,
        raise_status: bool = True,
        force_refresh: bool = False,
        times: int = 1,
    ) -> typing.Any:
        if not headers:
            headers = {}
        if not params:
            params = {}

        # refresh token as needed
        await self.refresh_tokens(force_refresh=force_refresh)

        async with self.session.request(
            method,
            f"{self.base_url}{url}",
            headers=headers | self.BASE_HEADERS,
            json=json,
            data=data,
            params=params,
        ) as resp:
            if resp.status == 401:  # unauthorized
                return await self.request(
                    method, url, data, force_refresh=True, times=times
                )
            if resp.status == 502 and times < 4:  # bad gateway
                await asyncio.sleep(1)
                return await self.request(
                    method, url, data, force_refresh=True, times=times + 1
                )

            try:
                if raise_status:
                    resp.raise_for_status()

                return (
                    None if resp.status == 204 else await resp.json(loads=orjson.loads)
                )
            except Exception as e:
                raise MicrosoftAPIException(resp, e) from e

    async def get(
        self,
        url: str,
        json: typing.Any = None,
        data: typing.Optional[dict] = None,
        params: typing.Optional[dict] = None,
        headers: typing.Optional[dict] = None,
    ) -> typing.Any:
        return await self.request(
            "GET", url, json=json, data=data, params=params, headers=headers
        )

    async def post(
        self,
        url: str,
        json: typing.Any = None,
        data: typing.Optional[dict] = None,
        params: typing.Optional[dict] = None,
        headers: typing.Optional[dict] = None,
    ) -> typing.Any:
        return await self.request(
            "POST", url, json=json, data=data, params=params, headers=headers
        )

    async def delete(
        self,
        url: str,
        json: typing.Any = None,
        data: typing.Optional[dict] = None,
        params: typing.Optional[dict] = None,
        headers: typing.Optional[dict] = None,
    ) -> typing.Any:
        return await self.request(
            "DELETE", url, json=json, data=data, params=params, headers=headers
        )
