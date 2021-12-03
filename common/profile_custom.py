"""
Profile

Get Userprofiles by XUID or Gamertag
"""
from typing import List

from aiohttp import ClientResponse
from xbox.webapi.api.provider.baseprovider import BaseProvider
from xbox.webapi.api.provider.profile.models import ProfileSettings


class ProfileProvider(BaseProvider):
    PROFILE_URL = "https://profile.xboxlive.com"
    HEADERS_PROFILE = {"x-xbl-contract-version": "3"}
    SEPARATOR = ","

    async def get_profiles(self, xuid_list: List[str], **kwargs) -> ClientResponse:
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
        url = self.PROFILE_URL + "/users/batch/profile/settings"
        resp = await self.client.session.post(
            url, json=post_data, headers=self.HEADERS_PROFILE, **kwargs
        )

        return resp  # dirty patch to make sure this works
