from dataclasses import dataclass

import apischema

__all__ = ("Setting", "ProfileUser", "ProfileResponse", "parse_profile_response")


@dataclass
class Setting:
    id: str
    value: str


@dataclass
class ProfileUser:
    id: str
    host_id: str
    settings: list[Setting]
    is_sponsored_user: bool


@dataclass
class ProfileResponse:
    profile_users: list[ProfileUser]


def parse_profile_response(resp: dict) -> ProfileResponse:
    return apischema.deserialize(ProfileResponse, resp)
