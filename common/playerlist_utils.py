"""
Copyright 2020-2023 AstreaTSS.
This file is part of the Realms Playerlist Bot.

The Realms Playerlist Bot is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

The Realms Playerlist Bot is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with the Realms
Playerlist Bot. If not, see <https://www.gnu.org/licenses/>.
"""

import asyncio
import contextlib
import logging
import os
import typing
from collections import defaultdict

import aiohttp
import aiohttp_retry
import attrs
import elytra
import interactions as ipy
import orjson
from msgspec import ValidationError
from redis.asyncio.client import Pipeline

import common.models as models
import common.utils as utils

logger = logging.getLogger("realms_bot")


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
        super().__init__("The gamertag handler is on cooldown.")


class GamertagInfo(typing.NamedTuple):
    gamertag: str
    device: str | None = None


@attrs.define()
class GamertagHandler:
    """
    A special class made to handle the complexities of getting gamertags
    from XUIDs.
    """

    bot: utils.RealmBotBase = attrs.field()
    sem: asyncio.Semaphore = attrs.field()
    xuids_to_get: tuple[str, ...] = attrs.field()
    openxbl_session: aiohttp_retry.RetryClient = attrs.field()
    gather_devices_for: set[str] = attrs.field(kw_only=True, factory=set)

    index: int = attrs.field(init=False, default=0)
    responses: list[elytra.ProfileResponse | elytra.PeopleHubResponse] = attrs.field(
        init=False, factory=list
    )
    AMOUNT_TO_GET: int = attrs.field(init=False, default=500)

    def __attrs_post_init__(self) -> None:
        # filter out empty strings, because that's possible somehow?
        self.xuids_to_get = tuple(x for x in self.xuids_to_get if x)

    async def get_gamertags(self, xuid_list: list[str]) -> None:
        # this endpoint is absolutely op and should rarely fail
        # franky, we usually don't need the backup thing, but you can't go wrong
        # having it

        try:
            people = await self.bot.xbox.fetch_people_batch(
                xuid_list, dont_handle_ratelimit=True
            )

        except elytra.MicrosoftAPIException as e:
            people_json = await e.resp.json(loads=orjson.loads)

            if people_json.get("code"):  # usually means ratelimited or invalid xuid
                description: str = people_json["description"]

                if description.startswith("Throttled"):  # ratelimited
                    raise GamertagOnCooldown() from e

                # otherwise, invalid xuid
                desc_split = description.split(" ")
                xuid_list.remove(desc_split[1])

                # after removing, try getting data again
                return await self.get_gamertags(xuid_list)

            if people_json.get("limitType"):  # ratelimit
                raise GamertagOnCooldown() from e

            else:
                raise

        self.responses.append(people)
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
                    r.raise_for_status()

                    self.responses.append(await elytra.ProfileResponse.from_response(r))
                except (
                    aiohttp.ContentTypeError,
                    aiohttp.ClientResponseError,
                    ValidationError,
                ):
                    # can happen, if not rare
                    text = await r.text()
                    logger.info(
                        f"Failed to get gamertag of user `{xuid}`.\nResponse code:"
                        f" {r.status}\nText: {text}"
                    )

            self.index += 1

    def _handle_new_gamertag(
        self,
        pipe: Pipeline,
        xuid: str,
        gamertag: str,
        dict_gamertags: dict[str, GamertagInfo],
        *,
        device: str | None = None,
    ) -> dict[str, GamertagInfo]:
        if not xuid or not gamertag:
            return dict_gamertags

        dict_gamertags[xuid] = GamertagInfo(gamertag, device)

        pipe.setex(name=xuid, time=utils.EXPIRE_GAMERTAGS_AT, value=gamertag)
        pipe.setex(name=f"rpl-{gamertag}", time=utils.EXPIRE_GAMERTAGS_AT, value=xuid)

        return dict_gamertags

    async def _execute_pipeline(self, pipe: Pipeline) -> None:
        try:
            await pipe.execute()
        finally:
            await pipe.reset()

    async def run(self) -> dict[str, GamertagInfo]:
        while self.index < len(self.xuids_to_get):
            current_xuid_list = list(
                self.xuids_to_get[self.index : self.index + self.AMOUNT_TO_GET]
            )

            async with self.sem:
                try:
                    await self.get_gamertags(current_xuid_list)
                except (
                    GamertagOnCooldown,
                    ValidationError,
                    elytra.MicrosoftAPIException,
                ):
                    # hopefully fixes itself in 15 seconds
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(self.backup_get_gamertags(), timeout=15)

        dict_gamertags: dict[str, GamertagInfo] = {}
        pipe = self.bot.redis.pipeline()

        try:
            for response in self.responses:
                if isinstance(response, elytra.PeopleHubResponse):
                    for user in response.people:
                        device = None
                        if (
                            user.xuid in self.gather_devices_for
                            and user.presence_details
                        ) and (
                            a_match := next(
                                (
                                    p
                                    for p in user.presence_details
                                    if (p.is_primary or p.state == "Active")
                                ),
                                None,
                            )
                        ):
                            device = a_match.device

                        dict_gamertags = self._handle_new_gamertag(
                            pipe,
                            user.xuid,
                            user.gamertag,
                            dict_gamertags,
                            device=device,
                        )
                else:
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

                        dict_gamertags = self._handle_new_gamertag(
                            pipe, xuid, gamertag, dict_gamertags
                        )

            # send data to pipeline in background
            self.bot.create_task(self._execute_pipeline(pipe))
        except:
            await pipe.reset()
            raise

        return dict_gamertags


async def has_linked_realm(ctx: utils.RealmContext) -> bool:
    guild_config = await ctx.fetch_config()

    if not guild_config.realm_id:
        raise utils.CustomCheckFailure(
            "This server is not linked to any Realm. Please check out [the Server"
            f" Setup Guide]({os.environ['SETUP_LINK']}) for more information."
        )
    return True


async def has_playerlist_channel(ctx: utils.RealmContext) -> bool:
    guild_config = await ctx.fetch_config()

    if not guild_config.playerlist_chan:
        raise utils.CustomCheckFailure(
            "This server does not have a playerlist channel set up. Please check out"
            f" [the Server Setup Guide]({os.environ['SETUP_LINK']}) for more"
            " information."
        )
    return True


async def invalidate_premium(
    bot: utils.RealmBotBase,
    config: models.GuildConfig,
) -> None:
    if config.valid_premium:
        config.premium_code = None
    config.live_playerlist = False
    config.fetch_devices = False
    config.live_online_channel = None

    await config.save()

    if config.realm_id:
        bot.live_playerlist_store[config.realm_id].discard(config.guild_id)
        if not await models.GuildConfig.prisma().count(
            where={"realm_id": config.realm_id, "fetch_devices": True}
        ):
            bot.fetch_devices_for.discard(config.realm_id)


async def eventually_invalidate(
    bot: utils.RealmBotBase,
    guild_config: models.GuildConfig,
    limit: int = 3,
) -> None:
    if not utils.FEATURE("EVENTUALLY_INVALIDATE"):
        return

    # the idea here is to invalidate autorunners that simply can't be run
    # there's a bit of generousity here, as the code gives a total of limit tries
    # before actually doing it
    num_times = await bot.redis.incr(
        f"invalid-playerlist{limit}-{guild_config.guild_id}"
    )

    logger.info(
        f"Increased invalid-playerlist for guild {guild_config.guild_id} to"
        f" {num_times}/{limit}."
    )

    # expire time - one day plus a bit of leeway
    await bot.redis.expire(f"invalid-playerlist{limit}-{guild_config.guild_id}", 87400)

    if num_times >= limit:
        logger.info(
            f"Unlinking guild {guild_config.guild_id} with"
            f" {num_times}/{limit} invalidations."
        )

        # ALL of this is just to reset the config so that there's no more
        # playerlist channel info
        old_playerlist_chan = guild_config.playerlist_chan
        guild_config.playerlist_chan = None
        old_live_playerlist = guild_config.live_playerlist
        guild_config.live_playerlist = False
        old_watchlist = guild_config.player_watchlist
        guild_config.player_watchlist = []
        guild_config.player_watchlist_role = None
        guild_config.notification_channels = {}
        await guild_config.save()
        await bot.redis.delete(
            f"invalid-playerlist3-{guild_config.guild_id}",
            f"invalid-playerlist7-{guild_config.guild_id}",
        )

        if guild_config.realm_id and old_watchlist:
            for player_xuid in old_watchlist:
                bot.player_watchlist_store[
                    f"{guild_config.realm_id}-{player_xuid}"
                ].discard(guild_config.guild_id)

        if guild_config.realm_id and old_live_playerlist:
            bot.live_playerlist_store[guild_config.realm_id].discard(
                guild_config.guild_id
            )

        if old_playerlist_chan:
            with contextlib.suppress(ipy.errors.HTTPException, AttributeError):
                chan = utils.partial_channel(bot, old_playerlist_chan)

                msg = (
                    "The playerlist channel has been unlinked as the bot has not been"
                    " able to properly send messages to it. Please check your"
                    " permissions, make sure the bot has `View Channel`, `Send"
                    " Messages`, and `Embed Links` enabled, and then re-set the"
                    " playerlist channel."
                )

                await chan.send(msg)


# TODO: combine these into one somehow
async def eventually_invalidate_watchlist(
    bot: utils.RealmBotBase, guild_config: models.GuildConfig
) -> None:
    if not utils.FEATURE("EVENTUALLY_INVALIDATE"):
        return

    num_times = await bot.redis.incr(f"invalid-watchlist-{guild_config.guild_id}")

    logger.info(
        f"Increased invalid-watchlist for guild {guild_config.guild_id} to"
        f" {num_times}/3."
    )

    await bot.redis.expire(f"invalid-watchlist-{guild_config.guild_id}", 87400)

    if num_times >= 3:
        logger.info(
            f"Unlinking watchlist for guild {guild_config.guild_id} with"
            f" {num_times}/3 invalidations."
        )

        old_watchlist = guild_config.player_watchlist
        guild_config.player_watchlist = []
        guild_config.player_watchlist_role = None
        old_chan = guild_config.notification_channels.pop("player_watchlist", None)
        await guild_config.save()

        if guild_config.realm_id and old_watchlist:
            for player_xuid in old_watchlist:
                bot.player_watchlist_store[
                    f"{guild_config.realm_id}-{player_xuid}"
                ].discard(guild_config.guild_id)

        if old_chan:
            with contextlib.suppress(ipy.errors.HTTPException, AttributeError):
                chan = utils.partial_channel(bot, old_chan)

                msg = (
                    "The player watchlist players and channel has been unlinked as the"
                    " bot has not been able to properly send messages to it. Please"
                    " check your permissions, make sure the bot has `View Channel`,"
                    " `Send Messages`, and `Embed Links` enabled, and then re-set the"
                    " watchlist and channel."
                )

                await chan.send(msg)


async def eventually_invalidate_realm_offline(
    bot: utils.RealmBotBase, guild_config: models.GuildConfig
) -> None:
    if not utils.FEATURE("EVENTUALLY_INVALIDATE"):
        return

    num_times = await bot.redis.incr(f"invalid-realm-offline-{guild_config.guild_id}")

    logger.info(
        f"Increased invalid-realm-offline for guild {guild_config.guild_id} to"
        f" {num_times}/3."
    )

    await bot.redis.expire(f"invalid-realm-offline-{guild_config.guild_id}", 87400)

    if num_times >= 3:
        logger.info(
            f"Unlinking Realm offline for guild {guild_config.guild_id} with"
            f" {num_times}/3 invalidations."
        )

        guild_config.realm_offline_role = None
        old_chan = guild_config.notification_channels.pop("realm_offline", None)
        await guild_config.save()

        if old_chan:
            with contextlib.suppress(ipy.errors.HTTPException, AttributeError):
                chan = utils.partial_channel(bot, old_chan)

                msg = (
                    "The Realm Offline role and channel has been unlinked as the bot"
                    " has not been able to properly send messages to it. Please check"
                    " your permissions, make sure the bot has `View Channel`, `Send"
                    " Messages`, and `Embed Links` enabled, and then re-set the role"
                    " and channel."
                )

                await chan.send(msg)


async def eventually_invalidate_live_online(
    bot: utils.RealmBotBase,
    guild_config: models.GuildConfig,
) -> None:
    if not utils.FEATURE("EVENTUALLY_INVALIDATE"):
        return

    num_times = await bot.redis.incr(f"invalid-liveonline-{guild_config.guild_id}")
    await bot.redis.expire(f"invalid-liveonline-{guild_config.guild_id}", 86400)

    if num_times >= 3:
        guild_config.live_online_channel = None
        await guild_config.save()
        await bot.redis.delete(f"invalid-liveonline-{guild_config.guild_id}")


async def fill_in_gamertags_for_sessions(
    bot: utils.RealmBotBase,
    player_sessions: list[models.PlayerSession],
    *,
    bypass_cache: bool = False,
    bypass_cache_for: set[str] | None = None,
) -> list[models.PlayerSession]:
    session_dict = {session.xuid: session for session in player_sessions}
    unresolved: list[str] = []

    if bypass_cache_for is None:
        bypass_cache_for = set()

    if not bypass_cache:
        async with bot.redis.pipeline() as pipeline:
            for session in player_sessions:
                if session.xuid not in bypass_cache_for:
                    pipeline.get(session.xuid)
                else:
                    # yes, this is dumb. yes, it works
                    pipeline.get("PURPOSELY_INVALID_KEY_AAAAAAAAAAAAAAAA")

            gamertag_list: list[str | None] = await pipeline.execute()

        # order is important to keep while iterating
        # hence the PURPOSELY_INVALID_KEY_AAAAAAAAAAAAAAAA earlier
        # TODO: make this ordering indepenent
        for index, xuid in enumerate(session_dict.keys()):
            gamertag = gamertag_list[index]
            session_dict[xuid].gamertag = gamertag

            if not gamertag:
                unresolved.append(xuid)
    else:
        unresolved = list(session_dict.keys())
        bypass_cache_for = set(unresolved)

    if unresolved:
        gamertag_handler = GamertagHandler(
            bot,
            bot.pl_sem,
            tuple(unresolved),
            bot.openxbl_session,
            gather_devices_for=bypass_cache_for,
        )
        gamertag_dict = await gamertag_handler.run()

        for xuid, gamertag_info in gamertag_dict.items():
            session_dict[xuid].gamertag = gamertag_info.gamertag
            session_dict[xuid].device = gamertag_info.device

    return list(session_dict.values())


async def get_xuid_to_gamertag_map(
    bot: utils.RealmBotBase,
    xuid_list: list[str],
) -> defaultdict[str, str]:
    gamertag_map: defaultdict[str, str] = defaultdict(lambda: "")

    unresolved: list[str] = []

    async with bot.redis.pipeline() as pipeline:
        for xuid in xuid_list:
            pipeline.get(xuid)

        gamertag_list: list[str | None] = await pipeline.execute()

    for index, xuid in enumerate(xuid_list):
        gamertag = gamertag_list[index]

        if not gamertag:
            unresolved.append(xuid)
            continue

        gamertag_map[xuid] = gamertag

    if unresolved:
        gamertag_handler = GamertagHandler(
            bot,
            bot.pl_sem,
            tuple(unresolved),
            bot.openxbl_session,
        )
        gamertag_dict = await gamertag_handler.run()

        for xuid, gamertag_info in gamertag_dict.items():
            gamertag_map[xuid] = gamertag_info.gamertag

    return gamertag_map


async def gamertag_from_xuid(bot: utils.RealmBotBase, xuid: str | int) -> str:
    if gamertag := await bot.redis.get(str(xuid)):
        return gamertag

    maybe_gamertag: elytra.ProfileResponse | None = None

    with contextlib.suppress(
        aiohttp.ClientResponseError,
        asyncio.TimeoutError,
        ValidationError,
        elytra.MicrosoftAPIException,
    ):
        maybe_gamertag = await bot.xbox.fetch_profile_by_xuid(xuid)

    if not maybe_gamertag:
        async with bot.openxbl_session.get(
            f"https://xbl.io/api/v2/account/{xuid}"
        ) as r:
            try:
                r.raise_for_status()
                maybe_gamertag = await elytra.ProfileResponse.from_response(r)
            except (
                aiohttp.ContentTypeError,
                aiohttp.ClientResponseError,
                ValidationError,
            ):
                # can happen, if not rare
                text = await r.text()
                logger.info(
                    f"Failed to get gamertag of user `{xuid}`.\nResponse code:"
                    f" {r.status}\nText: {text}"
                )

    if not maybe_gamertag:
        raise ipy.errors.BadArgument(f"`{xuid}` is not a valid XUID.")

    gamertag = next(
        s.value for s in maybe_gamertag.profile_users[0].settings if s.id == "Gamertag"
    )

    async with bot.redis.pipeline() as pipe:
        pipe.setex(
            name=str(xuid),
            time=utils.EXPIRE_GAMERTAGS_AT,
            value=gamertag,
        )
        pipe.setex(
            name=f"rpl-{gamertag}",
            time=utils.EXPIRE_GAMERTAGS_AT,
            value=str(xuid),
        )
        await pipe.execute()

    return gamertag


async def xuid_from_gamertag(bot: utils.RealmBotBase, gamertag: str) -> str:
    if xuid := await bot.redis.get(f"rpl-{gamertag}"):
        return xuid

    maybe_xuid: elytra.ProfileResponse | None = None

    with contextlib.suppress(
        aiohttp.ClientResponseError,
        asyncio.TimeoutError,
        ValidationError,
        elytra.MicrosoftAPIException,
    ):
        maybe_xuid = await bot.xbox.fetch_profile_by_gamertag(gamertag)

    if not maybe_xuid:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=2.5)
        ) as session:
            headers = {
                "X-Authorization": os.environ["OPENXBL_KEY"],
                "Accept": "application/json",
                "Accept-Language": "en-US",
            }
            with contextlib.suppress(asyncio.TimeoutError):
                async with session.get(
                    f"https://xbl.io/api/v2/search/{gamertag}",
                    headers=headers,
                ) as r:
                    with contextlib.suppress(ValidationError, aiohttp.ContentTypeError):
                        maybe_xuid = await elytra.ProfileResponse.from_response(r)

    if not maybe_xuid:
        raise ipy.errors.BadArgument(f"`{gamertag}` is not a valid gamertag.")

    xuid = maybe_xuid.profile_users[0].id

    async with bot.redis.pipeline() as pipe:
        pipe.setex(
            name=str(xuid),
            time=utils.EXPIRE_GAMERTAGS_AT,
            value=gamertag,
        )
        pipe.setex(
            name=f"rpl-{gamertag}",
            time=utils.EXPIRE_GAMERTAGS_AT,
            value=str(xuid),
        )
        await pipe.execute()

    return xuid
