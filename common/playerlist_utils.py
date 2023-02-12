import asyncio
import contextlib
import logging

import aiohttp
import attrs
import naff
import orjson
from apischema import ValidationError
from redis.asyncio.client import Pipeline
from tortoise.exceptions import DoesNotExist

import common.classes as cclasses
import common.models as models
import common.utils as utils
import common.xbox_api as xbox_api


def _convert_fields(value: tuple[str, ...] | None) -> tuple[str, ...]:
    return ("online", "last_seen") + value if value else ("online", "last_seen")


class RealmPlayersContainer:
    __slots__ = ("player_sessions", "fields")

    player_sessions: list[models.PlayerSession]
    fields: tuple[str, ...]

    def __init__(
        self,
        *,
        player_sessions: list[models.PlayerSession],
        fields: tuple[str, ...] | None = None,
    ) -> None:
        self.player_sessions = player_sessions
        self.fields = _convert_fields(fields)


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
    xuids_to_get: tuple[str, ...] = attrs.field()
    openxbl_session: aiohttp.ClientSession = attrs.field()

    index: int = attrs.field(init=False, default=0)
    responses: list[xbox_api.ProfileResponse | xbox_api.PeopleHubResponse] = (
        attrs.field(init=False, factory=list)
    )
    AMOUNT_TO_GET: int = attrs.field(init=False, default=500)

    def __attrs_post_init__(self) -> None:
        # filter out empty strings, because that's possible somehow?
        self.xuids_to_get = tuple(x for x in self.xuids_to_get if x)

    async def get_gamertags(self, xuid_list: list[str]) -> None:
        # this endpoint is absolutely op and should rarely fail
        # franky, we usually don't need the backup thing, but you can't go wrong
        # having it
        people_json = await self.bot.xbox.fetch_people_batch(xuid_list)

        if people_json.get("code"):  # usually means ratelimited or invalid xuid
            description: str = people_json["description"]

            if description.startswith("Throttled"):  # ratelimited
                raise GamertagOnCooldown()

            # otherwise, invalid xuid
            desc_split = description.split(" ")
            xuid_list.remove(desc_split[1])

            await self.get_gamertags(
                xuid_list
            )  # after removing, try getting data again

        elif people_json.get("limitType"):  # ratelimit
            raise GamertagOnCooldown()

        self.responses.append(xbox_api.parse_peoplehub_reponse(people_json))
        self.index += self.AMOUNT_TO_GET

    async def backup_get_gamertags(self) -> None:
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
                        (
                            f"Failed to get gamertag of user `{xuid}`.\nResponse code:"
                            f" {r.status}\nText: {text}"
                        ),
                    )

            self.index += 1

    def _handle_new_gamertag(
        self, pipe: Pipeline, xuid: str, gamertag: str, dict_gamertags: dict[str, str]
    ) -> None:
        if not xuid or not gamertag:
            return

        dict_gamertags[xuid] = gamertag

        pipe.setex(name=xuid, time=utils.EXPIRE_GAMERTAGS_AT, value=gamertag)
        pipe.setex(name=f"rpl-{gamertag}", time=utils.EXPIRE_GAMERTAGS_AT, value=xuid)

    async def _execute_pipeline(self, pipe: Pipeline) -> None:
        try:
            await pipe.execute()
        finally:
            await pipe.reset()

    async def run(self) -> dict[str, str]:
        while self.index < len(self.xuids_to_get):
            current_xuid_list = list(
                self.xuids_to_get[self.index : self.index + self.AMOUNT_TO_GET]
            )

            async with self.sem:
                try:
                    await self.get_gamertags(current_xuid_list)
                except GamertagOnCooldown:
                    # hopefully fixes itself in 15 seconds
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(self.backup_get_gamertags(), timeout=15)

        dict_gamertags: dict[str, str] = {}
        pipe = self.bot.redis.pipeline()

        try:
            for response in self.responses:
                if isinstance(response, xbox_api.PeopleHubResponse):
                    for user in response.people:
                        self._handle_new_gamertag(
                            pipe, user.xuid, user.gamertag, dict_gamertags
                        )
                elif isinstance(response, xbox_api.ProfileResponse):
                    for user in response.profile_users:
                        xuid = user.id
                        try:
                            # really funny but efficient way of getting gamertag
                            # from this data
                            gamertag = next(
                                s.value for s in user.settings if s.id == "Gamertag"
                            )
                        except (KeyError, StopIteration):
                            continue

                        self._handle_new_gamertag(pipe, xuid, gamertag, dict_gamertags)

            # send data to pipeline in background
            asyncio.create_task(self._execute_pipeline(pipe))
        except:
            await pipe.reset()
            raise

        return dict_gamertags


async def can_run_playerlist(ctx: utils.RealmContext) -> bool:
    # simple check to see if a person can run the playerlist command
    try:
        guild_config = await ctx.fetch_config()
    except DoesNotExist:
        return False
    return bool(guild_config.realm_id)


async def eventually_invalidate(
    bot: utils.RealmBotBase,
    guild_config: models.GuildConfig,
    limit: int = 3,
) -> None:
    if utils.TEST_MODE:
        return

    # the idea here is to invalidate autorunners that simply can't be run
    # there's a bit of generousity here, as the code gives a total of 3 tries
    # before actually doing it
    num_times = await bot.redis.get(
        f"invalid-playerlist{limit}-{guild_config.guild_id}"
    )

    if not num_times:
        num_times = "0"
    int_num_times = int(num_times) + 1

    if int_num_times >= limit:
        guild_config.playerlist_chan = None
        old_live_playerlist = guild_config.live_playerlist
        guild_config.live_playerlist = False
        await guild_config.save()
        await bot.redis.delete(f"invalid-playerlist{limit}-{guild_config.guild_id}")

        logging.getLogger("realms_bot").info(
            f"Unlinked guild {guild_config.guild_id} with {limit} invalidations."
        )

        if guild_config.realm_id and old_live_playerlist:
            bot.live_playerlist_store[guild_config.realm_id].discard(
                guild_config.guild_id
            )
    else:
        await bot.redis.set(
            f"invalid-playerlist{limit}-{guild_config.guild_id}",
            str(int_num_times),
            ex=limit * 86400,  # limit times day
        )


async def eventually_invalidate_realm_offline(
    bot: utils.RealmBotBase,
    guild_config: models.GuildConfig,
    limit: int = 3,
) -> None:
    if utils.TEST_MODE:
        return

    num_times = await bot.redis.incr(f"invalid-realmoffline-{guild_config.guild_id}")

    if num_times >= limit:
        guild_config.realm_offline_role = None
        await guild_config.save()
        await bot.redis.delete(f"invalid-realmoffline-{guild_config.guild_id}")


async def fetch_playerlist_channel(
    bot: utils.RealmBotBase, guild: naff.Guild, config: models.GuildConfig
) -> utils.GuildMessageable:
    try:
        chan = await guild.fetch_channel(config.playerlist_chan)  # type: ignore
    except naff.errors.HTTPException as e:
        if e.status < 500:  # over 500 is a discord fault
            await eventually_invalidate(bot, config)
        raise ValueError() from None
    except TypeError:  # playerlist chan is none, do nothing
        raise ValueError() from None
    else:
        if not chan:
            # invalid channel
            await eventually_invalidate(bot, config)
            raise ValueError()

        try:
            chan = cclasses.valid_channel_check(chan)
        except naff.errors.BadArgument:
            await eventually_invalidate(bot, config)
            raise ValueError() from None

    return chan


async def fill_in_gamertags_for_sessions(
    bot: utils.RealmBotBase,
    player_sessions: list[models.PlayerSession],
) -> list[models.PlayerSession]:
    session_dict = {session.xuid: session for session in player_sessions}
    unresolved: list[str] = []

    async with bot.redis.pipeline() as pipeline:
        for session in player_sessions:
            pipeline.get(session.xuid)
        gamertag_list: list[str | None] = await pipeline.execute()

    for index, xuid in enumerate(session_dict.keys()):
        gamertag = gamertag_list[index]
        session_dict[xuid].gamertag = gamertag

        if not gamertag:
            unresolved.append(xuid)

    if unresolved:
        gamertag_handler = GamertagHandler(
            bot,
            bot.pl_sem,
            tuple(unresolved),
            bot.openxbl_session,
        )
        gamertag_dict = await gamertag_handler.run()

        for xuid, gamertag in gamertag_dict.items():
            session_dict[xuid].gamertag = gamertag

    return list(session_dict.values())
