import orjson
from aiohttp import ClientResponse
from xbox.webapi.api.provider.baseprovider import BaseProvider
from xbox.webapi.api.provider.profile.models import ProfileSettings
from xbox.webapi.common.models import CamelCaseModel
from xbox.webapi.common.models import PascalCaseModel


# monkeypatching to speed things up slightly


def to_pascal(string):
    return "".join(word.capitalize() for word in string.split("_"))


def to_camel(string):
    words = string.split("_")
    return words[0] + "".join(word.capitalize() for word in words[1:])


class PascalCaseModelConfig:
    arbitrary_types_allowed = True
    allow_population_by_field_name = True
    alias_generator = to_pascal
    json_loads = orjson.loads


class CamelCaseModelConfig:
    arbitrary_types_allowed = True
    allow_population_by_field_name = True
    alias_generator = to_camel
    json_loads = orjson.loads


PascalCaseModel.Config = PascalCaseModelConfig
CamelCaseModel.Config = CamelCaseModelConfig


class ProfileProvider(BaseProvider):
    PROFILE_URL = "https://profile.xboxlive.com"
    HEADERS_PROFILE = {"x-xbl-contract-version": "3"}
    SEPARATOR = ","

    async def get_profiles(self, xuid_list: list[str], **kwargs) -> ClientResponse:
        """
        Get profile info for list of xuids

        Args:
            xuid_list (list): List of xuids

        Returns:
            :class:`ProfileResponse`: Profile Response
        """
        post_data = {
            "settings": [ProfileSettings.GAMERTAG],
            "userIds": xuid_list,
        }
        url = f"{self.PROFILE_URL}/users/batch/profile/settings"
        resp = await self.client.session.post(
            url, json=post_data, headers=self.HEADERS_PROFILE, **kwargs
        )

        return resp  # dirty patch to make sure this works


class ClubProvider(BaseProvider):
    CLUB_URL = "https://clubhub.xboxlive.com"
    HEADERS_CLUB = {"x-xbl-contract-version": "4", "Accept-Language": "en-US"}

    async def get_club_user_presences(
        self, club_id: int | str, **kwargs
    ) -> ClientResponse:
        """
        Gets details about (at most) the last 1000 members active within a club.

        Args:
            club_id: id of club

        Returns:
            :class:`aiohttp.ClientResponse`: HTTP Response
        """

        url = f"{self.CLUB_URL}/clubs/Ids({club_id})/decoration/clubpresence"
        resp = await self.client.session.get(url, headers=self.HEADERS_CLUB, **kwargs)
        return resp
