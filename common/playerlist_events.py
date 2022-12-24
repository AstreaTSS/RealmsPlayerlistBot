import typing
from datetime import datetime

import attrs
import naff

import common.models as models
import common.playerlist_utils as pl_utils


@typing.dataclass_transform(
    eq_default=False,
    order_default=False,
    kw_only_default=False,
    field_specifiers=(attrs.field,),
)
def define():
    return attrs.define(eq=False, order=False, hash=False, kw_only=False)


@define()
class PlayerlistParseFinish(naff.events.BaseEvent):
    containers: tuple[pl_utils.RealmPlayersContainer, ...] = attrs.field(repr=False)


@define()
class PlayerlistEvent(naff.events.BaseEvent):
    realm_id: str = attrs.field(repr=False)

    @property
    def configs(self):
        return models.GuildConfig.filter(realm_id=self.realm_id)


@define()
class RealmDown(PlayerlistEvent):
    disconnected: set[str] = attrs.field(repr=False)
    last_seen: datetime = attrs.field(repr=False)


@define()
class LivePlayerlistSend(PlayerlistEvent):
    joined: set[str] = attrs.field(repr=False)
    left: set[str] = attrs.field(repr=False)
    last_seen: datetime = attrs.field(repr=False)


@define()
class WarnMissingPlayerlist(PlayerlistEvent):
    pass
