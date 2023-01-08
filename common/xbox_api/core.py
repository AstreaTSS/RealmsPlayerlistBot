import typing

import attrs

import common.utils as utils
from common.microsoft_core import BaseMicrosoftAPI

__all__ = ("XboxAPI",)


# more of a mini-api, but still
@attrs.define()
class XboxAPI(BaseMicrosoftAPI):
    relying_party: str = attrs.field(default=utils.XBOX_API_RELYING_PARTY)

    async def request(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return await super().request(*args, **kwargs, raise_status=False)

    async def fetch_profiles(self, xuid_list: list[str] | list[int]) -> dict:
        URL = "https://profile.xboxlive.com/users/batch/profile/settings"
        HEADERS = {"x-xbl-contract-version": "3"}

        post_data = {
            "settings": ["Gamertag"],
            "userIds": xuid_list,
        }
        return await self.post(URL, json=post_data, headers=HEADERS)  # type: ignore

    async def fetch_profile_by_xuid(self, target_xuid: str | int) -> dict:
        HEADERS = {"x-xbl-contract-version": "3"}
        PARAMS = {"settings": "Gamertag"}
        URL = f"https://profile.xboxlive.com/users/xuid({target_xuid})/profile/settings"
        return await self.get(URL, params=PARAMS, headers=HEADERS)  # type: ignore

    async def fetch_profile_by_gamertag(self, gamertag: str) -> dict:
        url = f"https://profile.xboxlive.com/users/gt({gamertag})/profile/settings"
        HEADERS = {"x-xbl-contract-version": "3"}
        PARAMS = {"settings": "Gamertag"}

        return await self.get(url, params=PARAMS, headers=HEADERS)  # type: ignore

    async def fetch_club_presences(self, club_id: int | str) -> dict:
        HEADERS = {"x-xbl-contract-version": "4", "Accept-Language": "en-US"}
        url = (
            f"https://clubhub.xboxlive.com/clubs/Ids({club_id})/decoration/clubpresence"
        )

        return await self.get(url, headers=HEADERS)  # type: ignore

    async def fetch_people_batch(
        self, xuid_list: list[str] | list[int], *, decoration: str = "presencedetail"
    ) -> dict:
        HEADERS = {"x-xbl-contract-version": "3", "Accept-Language": "en-US"}
        URL = f"https://peoplehub.xboxlive.com/users/me/people/batch/decoration/{decoration}"
        return await self.post(URL, headers=HEADERS, json={"xuids": xuid_list})
