import typing
from datetime import datetime
from enum import IntEnum
from uuid import UUID

import msgspec

import common.microsoft_core as mscore

__all__ = (
    "ClubUserPresence",
    "ClubDeeplinkMetadata",
    "ClubDeeplinks",
    "ClubPresence",
    "ClubType",
    "ProfileMetadata",
    "Profile",
    "TitleDeeplinkMetadata",
    "TitleDeeplinks",
    "Club",
    "ClubResponse",
)


def _camel_to_const_snake(s: str) -> str:
    return "".join([f"_{c}" if c.isupper() else c.upper() for c in s]).lstrip("_")


class ClubUserPresence(IntEnum):
    UNKNOWN = -1
    NOT_IN_CLUB = 0
    IN_CLUB = 1
    CHAT = 2
    FEED = 3
    ROSTER = 4
    PLAY = 5
    IN_GAME = 6

    @classmethod
    def from_xbox_api(cls, value: str) -> typing.Self:
        try:
            return cls[_camel_to_const_snake(value)]
        except KeyError:
            # it's not like i forgot a value, it's just that some are
            # literally not documented
            return cls.UNKNOWN


class ClubDeeplinkMetadata(mscore.CamelBaseModel):
    page_name: str
    uri: str


class ClubDeeplinks(mscore.CamelBaseModel):
    xbox: list[ClubDeeplinkMetadata]
    pc: list[ClubDeeplinkMetadata]


class ClubPresence(mscore.CamelBaseModel):
    xuid: str
    last_seen_timestamp: datetime
    _last_seen_state: str = msgspec.field(name="lastSeenState")

    @property
    def last_seen_state(self) -> ClubUserPresence:
        return ClubUserPresence.from_xbox_api(self._last_seen_state)


class ClubType(mscore.CamelBaseModel):
    type: str
    genre: str
    localized_title_family_name: str
    title_family_id: UUID


class ProfileMetadata(mscore.CamelBaseModel):
    can_viewer_change_setting: bool
    value: typing.Optional[typing.Any] = None
    allowed_values: typing.Optional[typing.Any] = None


class Profile(mscore.CamelBaseModel):
    description: ProfileMetadata
    rules: ProfileMetadata
    name: ProfileMetadata
    short_name: ProfileMetadata
    is_searchable: ProfileMetadata
    is_recommendable: ProfileMetadata
    request_to_join_enabled: ProfileMetadata
    open_join_enabled: ProfileMetadata
    leave_enabled: ProfileMetadata
    transfer_ownership_enabled: ProfileMetadata
    mature_content_enabled: ProfileMetadata
    watch_club_titles_only: ProfileMetadata
    display_image_url: ProfileMetadata
    background_image_url: ProfileMetadata
    preferred_locale: ProfileMetadata
    tags: ProfileMetadata
    associated_titles: ProfileMetadata
    primary_color: ProfileMetadata
    secondary_color: ProfileMetadata
    tertiary_color: ProfileMetadata


class TitleDeeplinkMetadata(mscore.CamelBaseModel):
    title_id: str
    uri: str = msgspec.field(name="Uri")


class TitleDeeplinks(mscore.BaseModel):
    xbox: list[TitleDeeplinkMetadata]
    pc: list[TitleDeeplinkMetadata]
    android: list[TitleDeeplinkMetadata]
    ios: list[TitleDeeplinkMetadata] = msgspec.field(
        name="iOS"
    )  # this makes more sense at least


class Club(mscore.CamelBaseModel):
    id: str
    club_type: ClubType
    creation_date_utc: datetime
    glyph_image_url: str
    banner_image_url: str
    followers_count: int
    members_count: int
    moderators_count: int
    recommended_count: int
    requested_to_join_count: int
    club_presence_count: int
    club_presence_today_count: int
    club_presence_in_game_count: int
    club_presence: list[ClubPresence]
    state: str
    report_count: int
    reported_items_count: int
    max_members_per_club: int
    max_members_in_game: int
    owner_xuid: str
    founder_xuid: str
    title_deeplinks: TitleDeeplinks
    profile: Profile
    club_deeplinks: ClubDeeplinks
    suspended_until_utc: typing.Optional[typing.Any] = None
    roster: typing.Optional[typing.Any] = None
    target_roles: typing.Optional[typing.Any] = None
    recommendation: typing.Optional[typing.Any] = None
    settings: typing.Optional[typing.Any] = None
    short_name: typing.Optional[typing.Any] = None


@mscore.add_decoder
class ClubResponse(mscore.ParsableCamelModel):
    clubs: list[Club]
    search_facet_results: typing.Optional[typing.Any] = None
    recommendation_counts: typing.Optional[typing.Any] = None
    club_deeplinks: typing.Optional[typing.Any] = None
