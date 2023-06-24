import typing
from enum import Enum
from types import NoneType

import common.microsoft_core as mscore
import common.utils as utils


class Permission(Enum):
    VISITOR = "VISITOR"
    MEMBER = "MEMBER"
    OPERATOR = "OPERATOR"


class State(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"


class WorldType(Enum):
    NORMAL = "NORMAL"


@mscore.add_decoder
class FullRealm(mscore.ParsableCamelModel):
    id: int
    remote_subscription_id: str
    owner: typing.Optional[str]
    name: str
    default_permission: Permission
    state: State
    days_left: int
    expired: bool
    expired_trial: bool
    grace_period: bool
    world_type: WorldType
    players: NoneType
    max_players: int
    minigame_name: NoneType
    minigame_id: NoneType
    minigame_image: NoneType
    active_slot: int
    slots: NoneType
    member: bool
    subscription_refresh_status: NoneType
    club_id: typing.Optional[int] = None
    owner_uuid: typing.Optional[str] = None
    motd: typing.Optional[str] = None


@mscore.add_decoder
class FullWorlds(mscore.ParsableModel):
    servers: list[FullRealm]


class Player(mscore.CamelBaseModel):
    uuid: str
    name: NoneType
    operator: bool
    accepted: bool
    online: bool
    permission: Permission


class PartialRealm(mscore.CamelBaseModel):
    id: int
    players: list[Player]
    full: bool


@mscore.add_decoder
class ActivityList(mscore.ParsableModel):
    servers: list[PartialRealm]


class RealmsAPI(mscore.BaseMicrosoftAPI):
    RELYING_PATH: str = utils.REALMS_API_URL
    BASE_URL: str = utils.REALMS_API_URL

    @property
    def base_headers(self) -> dict[str, str]:
        return {
            "Authorization": self.auth_mgr.xsts_token.authorization_header_value,
            "Client-Version": utils.MC_VERSION,
            "User-Agent": "MCPE/UWP",
        }

    async def join_realm_from_code(self, code: str) -> FullRealm:
        return FullRealm.from_bytes(await self.post(f"invites/v1/link/accept/{code}"))

    async def fetch_realms(self) -> FullWorlds:
        return FullWorlds.from_bytes(await self.get("worlds"))

    async def fetch_activities(self) -> ActivityList:
        return ActivityList.from_bytes(await self.get("activities/live/players"))

    async def leave_realm(self, realm_id: int | str) -> None:
        await self.delete(f"invites/{realm_id}")
