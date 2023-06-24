import typing
from datetime import datetime

import common.microsoft_core as mscore

__all__ = (
    "PeopleSummaryResponse",
    "Suggestion",
    "Recommendation",
    "MultiplayerSummary",
    "RecentPlayer",
    "Follower",
    "PreferredColor",
    "PresenceDetail",
    "TitlePresence",
    "Detail",
    "SocialManager",
    "Avatar",
    "LinkedAccount",
    "Person",
    "RecommendationSummary",
    "FriendFinderState",
    "PeopleHubResponse",
)


class PeopleSummaryResponse(mscore.CamelBaseModel):
    target_following_count: int
    target_follower_count: int
    is_caller_following_target: bool
    is_target_following_caller: bool
    has_caller_marked_target_as_favorite: bool
    has_caller_marked_target_as_identity_shared: bool
    legacy_friend_status: str
    available_people_slots: typing.Optional[int] = None
    recent_change_count: typing.Optional[int] = None
    watermark: typing.Optional[str] = None


# microsoft is a great and consistent company
class Suggestion(mscore.PascalBaseModel):
    priority: int
    type: typing.Optional[str] = None
    reasons: typing.Optional[str] = None
    title_id: typing.Optional[str] = None


class Recommendation(mscore.PascalBaseModel):
    type: str
    reasons: list[str]


class MultiplayerSummary(mscore.PascalBaseModel):
    in_multiplayer_session: int
    in_party: int


class RecentPlayer(mscore.CamelBaseModel):
    titles: list[str]
    text: typing.Optional[str] = None


class Follower(mscore.CamelBaseModel):
    text: typing.Optional[str] = None
    followed_date_time: typing.Optional[datetime] = None


class PreferredColor(mscore.CamelBaseModel):
    primary_color: typing.Optional[str] = None
    secondary_color: typing.Optional[str] = None
    tertiary_color: typing.Optional[str] = None


class PresenceDetail(mscore.PascalBaseModel):
    is_broadcasting: bool
    device: str
    presence_text: str
    state: str
    title_id: str
    is_primary: bool
    is_game: bool
    title_type: typing.Optional[str] = None
    rich_presence_text: typing.Optional[str] = None


class TitlePresence(mscore.PascalBaseModel):
    is_currently_playing: bool
    presence_text: typing.Optional[str] = None
    title_name: typing.Optional[str] = None
    title_id: typing.Optional[str] = None


class Detail(mscore.CamelBaseModel):
    account_tier: str
    is_verified: bool
    watermarks: list[str]
    blocked: bool
    mute: bool
    follower_count: int
    following_count: int
    has_game_pass: bool
    bio: typing.Optional[str] = None
    location: typing.Optional[str] = None
    tenure: typing.Optional[str] = None


class SocialManager(mscore.CamelBaseModel):
    title_ids: list[str]
    pages: list[str]


class Avatar(mscore.CamelBaseModel):
    update_time_offset: typing.Optional[datetime] = None
    spritesheet_metadata: typing.Optional[typing.Any] = None


class LinkedAccount(mscore.CamelBaseModel):
    network_name: str
    show_on_profile: bool
    is_family_friendly: bool
    display_name: typing.Optional[str] = None
    deeplink: typing.Optional[str] = None


class Person(mscore.CamelBaseModel):
    xuid: str
    is_favorite: bool
    is_following_caller: bool
    is_followed_by_caller: bool
    is_identity_shared: bool
    real_name: str
    display_pic_raw: str
    show_user_as_avatar: str
    gamertag: str
    gamer_score: str
    modern_gamertag: str
    modern_gamertag_suffix: str
    unique_modern_gamertag: str
    xbox_one_rep: str
    presence_state: str
    presence_text: str
    color_theme: str
    preferred_flag: str
    is_broadcasting: bool
    preferred_platforms: list[str]
    is_quarantined: bool
    is_xbox360_gamerpic: bool
    presence_devices: typing.Optional[typing.Any] = None
    is_cloaked: typing.Optional[bool] = None
    added_date_time_utc: typing.Optional[datetime] = None
    display_name: typing.Optional[str] = None
    suggestion: typing.Optional[Suggestion] = None
    recommendation: typing.Optional[Recommendation] = None
    search: typing.Optional[typing.Any] = None
    title_history: typing.Optional[typing.Any] = None
    multiplayer_summary: typing.Optional[MultiplayerSummary] = None
    recent_player: typing.Optional[RecentPlayer] = None
    follower: typing.Optional[Follower] = None
    preferred_color: typing.Optional[PreferredColor] = None
    presence_details: typing.Optional[list[PresenceDetail]] = None
    title_presence: typing.Optional[TitlePresence] = None
    title_summaries: typing.Optional[typing.Any] = None
    presence_title_ids: typing.Optional[list[str]] = None
    detail: typing.Optional[Detail] = None
    community_manager_titles: typing.Optional[typing.Any] = None
    social_manager: typing.Optional[SocialManager] = None
    broadcast: typing.Optional[list[typing.Any]] = None
    tournament_summary: typing.Optional[typing.Any] = None
    avatar: typing.Optional[Avatar] = None
    linked_accounts: typing.Optional[list[LinkedAccount]] = None
    last_seen_date_time_utc: typing.Optional[datetime] = None


class RecommendationSummary(mscore.CamelBaseModel):
    friend_of_friend: int
    facebook_friend: int
    phone_contact: int
    follower: int
    VIP: int
    steam_friend: int
    promote_suggestions: bool


class FriendFinderState(mscore.CamelBaseModel):
    facebook_opt_in_status: str
    facebook_token_status: str
    phone_opt_in_status: str
    phone_token_status: str
    steam_opt_in_status: str
    steam_token_status: str
    discord_opt_in_status: str
    discord_token_status: str
    instagram_opt_in_status: str
    instagram_token_status: str
    mixer_opt_in_status: str
    mixer_token_status: str
    reddit_opt_in_status: str
    reddit_token_status: str
    twitch_opt_in_status: str
    twitch_token_status: str
    twitter_opt_in_status: str
    twitter_token_status: str
    you_tube_opt_in_status: str
    you_tube_token_status: str


@mscore.add_decoder
class PeopleHubResponse(mscore.ParsableCamelModel):
    people: list[Person]
    recommendation_summary: typing.Optional[RecommendationSummary] = None
    friend_finder_state: typing.Optional[FriendFinderState] = None
    account_link_details: typing.Optional[list[LinkedAccount]] = None
