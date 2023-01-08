import asyncio
import contextlib
import datetime
import importlib
import os
import typing

import aiohttp
import naff
import orjson
import tansy
from apischema import ValidationError
from tortoise.exceptions import DoesNotExist

import common.graph_template as graph_template
import common.models as models
import common.stats_utils as stats_utils
import common.utils as utils
import common.xbox_api as xbox_api
from common.microsoft_core import MicrosoftAPIException

US_FORMAT = "%m/%d/%y %l %p"
INTERNATIONAL_FORMAT = "%d/%m/%y %k:%M"

showable_format = {
    US_FORMAT: "MM/DD/YY HH AM/PM",
    INTERNATIONAL_FORMAT: "DD/MM/YY HH:MM",
}


async def stats_check(ctx: utils.RealmContext) -> bool:
    try:
        guild_config = await ctx.fetch_config()
    except DoesNotExist:
        return False
    return guild_config.premium_code and guild_config.realm_id


class Statistics(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.name = "Statistics"

    async def xuid_from_gamertag(self, gamertag: str) -> str:
        maybe_xuid: typing.Union[
            str, xbox_api.ProfileResponse, None
        ] = await self.bot.redis.get(f"rpl-{gamertag}")

        if maybe_xuid:
            return maybe_xuid

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
                        maybe_xuid = xbox_api.parse_profile_response(
                            await r.json(loads=orjson.loads)
                        )

            if not maybe_xuid:
                with contextlib.suppress(
                    aiohttp.ClientResponseError,
                    asyncio.TimeoutError,
                    ValidationError,
                    MicrosoftAPIException,
                ):
                    resp = await self.bot.xbox.fetch_profile_by_gamertag(gamertag)
                    maybe_xuid = xbox_api.parse_profile_response(resp)

        if not maybe_xuid:
            raise naff.errors.BadArgument(f"`{gamertag}` is not a valid gamertag.")

        xuid = maybe_xuid.profile_users[0].id

        await self.bot.redis.setex(
            name=str(xuid),
            time=utils.EXPIRE_GAMERTAGS_AT,
            value=gamertag,
        )
        await self.bot.redis.setex(
            name=f"rpl-{gamertag}",
            time=utils.EXPIRE_GAMERTAGS_AT,
            value=str(xuid),
        )

        return xuid

    async def process_data(
        self,
        ctx: utils.RealmContext,
        config: models.GuildConfig,
        now: datetime.datetime,
        min_datetime: datetime.datetime,
        title: str,
        filter_kwargs: dict[str, typing.Any] | None = None,
        template_kwargs: dict[str, typing.Any] | None = None,
    ) -> None:
        if filter_kwargs is None:
            filter_kwargs = {}
        if template_kwargs is None:
            template_kwargs = {}

        datetimes_to_use: list[tuple[datetime.datetime, datetime.datetime]] = []

        async for entry in models.PlayerSession.filter(
            realm_id=config.realm_id, joined_at__gte=min_datetime, **filter_kwargs
        ):
            datetimes_to_use.append((entry.joined_at, entry.last_seen))  # type: ignore

        if not datetimes_to_use:
            raise utils.CustomCheckFailure(
                "There's no data on this user on the linked Realm for this timespan."
            )

        minutes_per_hour = stats_utils.get_minutes_per_hour(
            datetimes_to_use,
            min_datetime=min_datetime,
            max_datetime=now,
        )

        locale = ctx.locale or ctx.guild_locale or "en_GB"
        # im aware theres countries that do yy/mm/dd - i'll add them in soon
        locale_to_use = US_FORMAT if locale == "en-US" else INTERNATIONAL_FORMAT

        localized = {k.strftime(locale_to_use): v for k, v in minutes_per_hour.items()}
        url = graph_template.graph_template(
            title,
            showable_format[locale_to_use],
            tuple(localized.keys()),
            tuple(localized.values()),
            **template_kwargs,
        )

        embed = naff.Embed(
            color=self.bot.color,
            timestamp=now,  # type: ignore
        )
        embed.set_image(url)

        await ctx.send(embeds=embed)

    premium = tansy.SlashCommand(
        name="premium",  # type: ignore
        description="Handles the configuration for Realms Playerlist Premium.",  # type: ignore
        default_member_permissions=naff.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @premium.subcommand(
        sub_cmd_name="graph-individual-day",
        sub_cmd_description=(
            "Produces a graph of one player's playtime over one day as a graph. Beta,"
            " requires premium."
        ),
    )  # type: ignore
    @naff.cooldown(naff.Buckets.GUILD, 1, 5)  # type: ignore
    @naff.check(stats_check)  # type: ignore
    async def graph_individual_day(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the user to graph."),
    ) -> None:
        """
        Produces a graph of one player's playtime over the past day as a graph. Beta, requires premium.

        This command takes the total playtime of the player on the Realm over the past 24 hours,
        and graphs the player per hour.
        For example, if the player played for 20 minutes during the 5th hour, that will be graphed.

        This can be used to observe general activity trends for a player, although it currently does not
        aggregate the results - it only reads the last 24 hours, so if something unusual happened
        that day, it may produce a graph that does not line up with general activity.

        Has a cooldown of 5 seconds per server due to the calculations it makes.
        Only available to Premium members for now - this command is a WIP, and may change in the future.
        """
        config = await ctx.fetch_config()

        xuid = await self.xuid_from_gamertag(gamertag)

        now = datetime.datetime.now(datetime.UTC)
        one_day_ago = now - datetime.timedelta(days=1) + datetime.timedelta(minutes=1)

        await self.process_data(
            ctx,
            config,
            now,
            one_day_ago,
            f"Playtime of {gamertag} over the last 24 hours",
            filter_kwargs={"xuid": xuid},
        )

    @premium.subcommand(
        sub_cmd_name="graph-realm-day",
        sub_cmd_description=(
            "Produces a graph of the Realm's playtime over the past day as a graph."
            " Beta, requires premium."
        ),
    )
    @naff.cooldown(naff.Buckets.GUILD, 1, 5)  # type: ignore
    @naff.check(stats_check)  # type: ignore
    async def graph_realm_day(self, ctx: utils.RealmContext) -> None:
        """
        Produces a graph of the Realm's playtime over the past day as a graph. Beta, requires premium.

        This command takes the total playtime of every player on the Realm over the past 24 hours,
        and graphs the player per hour.
        To clarify: if two players were on the Realm for 10 minutes, they would have a combined total
        of 20 minutes of playtime.

        This can be used to observe general activity trends, although it currently does not
        aggregate the results - it only reads the last 24 hours, so if something unusual happened
        that day, it may produce a graph that does not line up with general activity.

        Has a cooldown of 5 seconds per server due to the calculations it makes.
        Only available to Premium members for now - this command is a WIP, and may change in the future.
        """
        config = await ctx.fetch_config()

        now = datetime.datetime.now(datetime.UTC)
        one_day_ago = now - datetime.timedelta(days=1) + datetime.timedelta(minutes=1)

        await self.process_data(
            ctx,
            config,
            now,
            one_day_ago,
            "Playtime on the Realm over the last 24 hours",
            template_kwargs={"max_value": None},
        )


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(stats_utils)
    importlib.reload(graph_template)
    importlib.reload(xbox_api)
    Statistics(bot)
