import asyncio
import contextlib
import datetime
import logging
import typing

import aiohttp
import attrs
import naff
import orjson
from apischema import ValidationError
from tortoise.exceptions import DoesNotExist

import common.models as models
import common.utils as utils
import common.xbox_api as xbox_api


@attrs.define(eq=False)
class Player:
    """A simple class to represent a player on a Realm."""

    xuid: str = attrs.field()
    last_seen: datetime.datetime = attrs.field()
    in_game: bool = attrs.field(default=False)
    gamertag: typing.Optional[str] = attrs.field(default=None)
    last_joined: typing.Optional[datetime.datetime] = attrs.field(default=None)

    def __eq__(self, o: object) -> bool:
        return o.xuid == self.xuid if isinstance(o, self.__class__) else False

    @property
    def resolved(self):
        return bool(self.gamertag)

    @property
    def base_display(self):
        return f"`{self.gamertag}`" if self.gamertag else f"User with XUID {self.xuid}"

    @property
    def display(self):  # sourcery skip: remove-unnecessary-else
        notes = []
        if self.last_joined:
            notes.append(
                f"joined {naff.Timestamp.fromdatetime(self.last_joined).format('f')}"
            )

        if not self.in_game:
            notes.append(
                f"left {naff.Timestamp.fromdatetime(self.last_seen).format('f')}"
            )

        return (
            f"{self.base_display}: {', '.join(notes)}" if notes else self.base_display
        )


class GamertagOnCooldown(Exception):
    # used by GamertagHandler to know when to switch to the backup
    def __init__(self) -> None:
        # i could make this anything since this should never be exposed
        # to the user, but who knows
        super().__init__("The gamertag handler is on cooldown!")


class GamertagServiceDown(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The gamertag service is down! The bot is unavailable at this time."
        )


@attrs.define()
class GamertagHandler:
    """A special class made to handle the complexities of getting gamertags
    from XUIDs."""

    bot: utils.RealmBotBase = attrs.field()
    sem: asyncio.Semaphore = attrs.field()
    xuids_to_get: typing.Tuple[str, ...] = attrs.field()
    openxbl_session: aiohttp.ClientSession = attrs.field()

    index: int = attrs.field(init=False, default=0)
    responses: list[xbox_api.ProfileResponse] = attrs.field(init=False, factory=list)
    AMOUNT_TO_GET: int = attrs.field(init=False, default=30)

    def __attrs_post_init__(self):
        # filter out empty strings, because that's possible somehow?
        self.xuids_to_get = tuple(x for x in self.xuids_to_get if x)

    async def get_gamertags(self, xuid_list: typing.List[str]) -> None:
        # honestly, i forget what this output can look like by now -
        # but if i remember, it's kinda weird
        profile_json = await self.bot.xbox.fetch_profiles(xuid_list)

        if profile_json.get("code"):  # usually means ratelimited or invalid xuid
            description: str = profile_json["description"]

            if description.startswith("Throttled"):  # ratelimited
                raise GamertagOnCooldown()

            # otherwise, invalid xuid
            desc_split = description.split(" ")
            xuid_list.remove(desc_split[1])

            await self.get_gamertags(
                xuid_list
            )  # after removing, try getting data again

        elif profile_json.get("limitType"):  # ratelimit
            raise GamertagOnCooldown()

        self.responses.append(xbox_api.parse_profile_response(profile_json))
        self.index += self.AMOUNT_TO_GET

    async def backup_get_gamertags(self):
        # openxbl is used throughout this, and its basically a way of navigating
        # the xbox live api in a more sane way than its actually laid out
        # while xbox-webapi-python can also do this without using a 3rd party service,
        # using openxbl can be more reliable at times as it has a generous 500 requests
        # per hour limit on the free tier and is not subject to ratelimits
        # however, there's no bulk xuid > gamertag option, and is a bit slow in general

        for xuid in self.xuids_to_get[self.index :]:
            async with self.openxbl_session.get(
                f"https://xbl.io/api/v2/account/{xuid}"
            ) as r:
                try:
                    resp_json = await r.json(loads=orjson.loads)
                    if "code" in resp_json.keys():  # service is down
                        await utils.msg_to_owner(self.bot, resp_json)
                        raise GamertagServiceDown()
                    else:
                        with contextlib.suppress(ValidationError):
                            self.responses.append(
                                xbox_api.parse_profile_response(resp_json)
                            )
                except aiohttp.ContentTypeError:
                    # can happen, if not rare
                    text = await r.text()
                    logging.getLogger(
                        "realms_bot"
                    ).info(  # this is more common than you would expect
                        f"Failed to get gamertag of user `{xuid}`.\nResponse code:"
                        f" {r.status}\nText: {text}",
                    )

            self.index += 1

    async def run(self):
        while self.index < len(self.xuids_to_get):
            current_xuid_list = list(self.xuids_to_get[self.index : self.index + 30])

            async with self.sem:
                with contextlib.suppress(GamertagOnCooldown):
                    await self.get_gamertags(current_xuid_list)
                # alright, so we either got 30 gamertags or are ratelimited
                # so now we switch to the backup getter so that we don't have
                # to wait on the ratelimit to request for more gamertags
                # this wait_for basically a little 'exploit` to only make the backup
                # run for 15 seconds or until completetion, whatever comes first
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self.backup_get_gamertags(), timeout=15)
        dict_gamertags: typing.Dict[str, str] = {}

        for profiles in self.responses:
            for user in profiles.profile_users:
                try:
                    # really funny but efficient way of getting gamertag
                    # from this data
                    gamertag = next(
                        s.value for s in user.settings if s.id == "Gamertag"
                    )
                    await self.bot.redis.setex(
                        name=str(user.id),
                        time=datetime.timedelta(days=14),
                        value=gamertag,
                    )
                    dict_gamertags[user.id] = gamertag
                except (KeyError, StopIteration):
                    continue

        return dict_gamertags


async def can_run_playerlist(ctx: utils.RealmContext) -> typing.Any:
    # simple check to see if a person can run the playerlist command
    try:
        guild_config = await ctx.fetch_config()
    except DoesNotExist:
        return False
    return bool(guild_config.club_id and guild_config.realm_id)


async def eventually_invalidate(
    bot: utils.RealmBotBase,
    guild_config: models.GuildConfig,
    limit=3,
):
    # the idea here is to invalidate autorunners that simply can't be run
    # there's a bit of generousity here, as the code gives a total of 3 tries
    # before actually doing it
    num_times = await bot.redis.incr(f"invalid-playerlist-{guild_config.guild_id}")

    if num_times > limit:
        guild_config.playerlist_chan = None
        await guild_config.save()
        await bot.redis.delete(f"invalid-playerlist-{guild_config.guild_id}")

        if guild_config.realm_id and guild_config.live_playerlist:
            bot.live_playerlist_store[guild_config.realm_id].discard(
                guild_config.guild_id
            )


async def fetch_playerlist_channel(
    bot: utils.RealmBotBase, guild: naff.Guild, config: models.GuildConfig
):
    try:
        chan = await guild.fetch_channel(config.playerlist_chan)  # type: ignore
    except naff.errors.HTTPException as e:
        await eventually_invalidate(bot, config)
        raise ValueError() from e
    else:
        if not chan or not isinstance(chan, naff.GuildText):
            # invalid channel
            await eventually_invalidate(bot, config)
            raise ValueError()

    return chan
