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
from tortoise.expressions import Q

import common.graph_template as graph_template
import common.help_tools as help_tools
import common.models as models
import common.stats_utils as stats_utils
import common.utils as utils
import common.xbox_api as xbox_api
from common.microsoft_core import MicrosoftAPIException

VALID_TIME_DICTS = typing.Union[
    dict[datetime.datetime, int], dict[datetime.date, int], dict[datetime.time, int]
]

US_FORMAT_TIME = "%l %p"
US_FORMAT_DATE = "%m/%d/%y"
US_FORMAT = f"{US_FORMAT_DATE} {US_FORMAT_TIME}"
INTERNATIONAL_FORMAT_TIME = "%k:%M"
INTERNATIONAL_FORMAT_DATE = "%d/%m/%y"
INTERNATIONAL_FORMAT = f"{INTERNATIONAL_FORMAT_DATE} {INTERNATIONAL_FORMAT_TIME}"

SHOWABLE_FORMAT = {
    US_FORMAT_TIME: "HH AM/PM",
    US_FORMAT_DATE: "MM/DD/YY",
    US_FORMAT: "MM/DD/YY HH AM/PM",
    INTERNATIONAL_FORMAT_TIME: "HH:MM",
    INTERNATIONAL_FORMAT_DATE: "DD/MM/YY",
    INTERNATIONAL_FORMAT: "DD/MM/YY HH:MM",
}

PERIOD_TO_GRAPH = [
    naff.SlashCommandChoice("One day, per hour", "1pH"),
    naff.SlashCommandChoice("1 week, per day", "7pD"),
    # naff.SlashCommandChoice("2 weeks, per day", "14pD"),
    # naff.SlashCommandChoice("30 days, per day", "30pD"),
    # naff.SlashCommandChoice("30 days, per week", "30pW"),
]

SUMMARIZE_BY = [
    naff.SlashCommandChoice("1 week, by hour", "7bH"),
    # naff.SlashCommandChoice("2 weeks, by hour", "14bH"),
    # naff.SlashCommandChoice("30 days, by hour", "30bH"),
    # naff.SlashCommandChoice("2 weeks, by day of the week", "14bD"),
    # naff.SlashCommandChoice("30 days, by day of the week", "30bD"),
]

DAY_HUMANIZED = {
    1: "24 hours",
    7: "1 week",
    14: "2 weeks",
    30: "30 days",
}


async def stats_check(ctx: utils.RealmContext) -> bool:
    try:
        guild_config = await ctx.fetch_config()
    except DoesNotExist:
        return False
    return bool(guild_config.premium_code and guild_config.realm_id)


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

        async with self.bot.redis.pipeline() as pipe:
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

    async def gather_datetimes(
        self,
        config: models.GuildConfig,
        min_datetime: datetime.datetime,
        **filter_kwargs: typing.Any,
    ) -> list[tuple[datetime.datetime, datetime.datetime]]:
        datetimes_to_use: list[tuple[datetime.datetime, datetime.datetime]] = []

        async for entry in models.PlayerSession.filter(
            realm_id=config.realm_id, joined_at__gte=min_datetime, **filter_kwargs
        ):
            datetimes_to_use.append((entry.joined_at, entry.last_seen))  # type: ignore

        if not datetimes_to_use:
            raise utils.CustomCheckFailure(
                "There's no data on this user on the linked Realm for this timespan."
            )

        return datetimes_to_use

    async def localize_and_send_graph(
        self,
        ctx: utils.RealmContext,
        raw_data: VALID_TIME_DICTS,
        title: str,
        scale_label: str,
        bottom_label: str,
        localizations: tuple[str, str],
        now: datetime.datetime,
        **template_kwargs: typing.Any,
    ) -> None:
        locale = ctx.locale or ctx.guild_locale or "en_GB"
        # im aware theres countries that do yy/mm/dd - i'll add them in soon
        locale_to_use = localizations[0] if locale == "en-US" else localizations[1]

        localized = {k.strftime(locale_to_use): v for k, v in raw_data.items()}
        url = graph_template.graph_template(
            title,
            scale_label,
            bottom_label.format(localized_format=SHOWABLE_FORMAT[locale_to_use]),
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

    async def process_graph(
        self,
        ctx: utils.RealmContext,
        *,
        config: models.GuildConfig,
        func_to_use: typing.Callable[..., VALID_TIME_DICTS],
        now: datetime.datetime,
        min_datetime: datetime.datetime,
        title: str,
        bottom_label: str,
        localizations: tuple[str, str],
        filter_kwargs: dict[str, typing.Any] | None = None,
        template_kwargs: dict[str, typing.Any] | None = None,
    ) -> None:
        if filter_kwargs is None:
            filter_kwargs = {}
        if template_kwargs is None:
            template_kwargs = {}

        datetimes_to_use = await self.gather_datetimes(
            config, min_datetime, **filter_kwargs
        )

        minutes_per_period = func_to_use(
            datetimes_to_use,
            min_datetime=min_datetime,
            max_datetime=now,
        )

        await self.localize_and_send_graph(
            ctx,
            minutes_per_period,
            title,
            "Total Minutes Played",
            bottom_label,
            localizations,
            now,
            **template_kwargs,
        )

    async def process_unsummary(
        self,
        ctx: utils.RealmContext,
        period: str,
        title: str,
        *,
        indivdual: bool = False,
        filter_kwargs: typing.Optional[dict[str, typing.Any]] = None,
    ) -> None:
        config = await ctx.fetch_config()

        template_kwargs = {"max_value": None}

        period_split = period.split("p")
        if len(period_split) != 2:
            raise naff.errors.BadArgument("Invalid period given.")

        try:
            num_days = int(period_split[0])
        except ValueError:
            raise naff.errors.BadArgument("Invalid period given.") from None

        actual_period = period_split[1]

        now = datetime.datetime.now(datetime.UTC)
        num_days_ago = (
            now - datetime.timedelta(days=num_days) + datetime.timedelta(minutes=1)
        )

        if actual_period == "H":
            func_to_use = stats_utils.get_minutes_per_hour
            bottom_label = "Date and Hour (UTC) in {localized_format}"
            localizations = (US_FORMAT, INTERNATIONAL_FORMAT)

            if indivdual:
                template_kwargs = {"max_value": 60}
        else:
            func_to_use = stats_utils.get_minutes_per_day
            bottom_label = "Date (UTC) in {localized_format}"
            localizations = (US_FORMAT_DATE, INTERNATIONAL_FORMAT_DATE)

        await self.process_graph(
            ctx,
            config=config,
            func_to_use=func_to_use,
            now=now,
            min_datetime=num_days_ago,
            title=title.format(days_humanized=DAY_HUMANIZED[num_days]),
            bottom_label=bottom_label,
            localizations=localizations,
            filter_kwargs=filter_kwargs,
            template_kwargs=template_kwargs,
        )

    async def process_summary(
        self,
        ctx: utils.RealmContext,
        summarize_by: str,
        title: str,
        *,
        filter_kwargs: typing.Optional[dict[str, typing.Any]] = None,
    ) -> None:
        config = await ctx.fetch_config()

        summary_split = summarize_by.split("b")
        if len(summary_split) != 2:
            raise naff.errors.BadArgument("Invalid summary given.")

        try:
            num_days = int(summary_split[0])
        except ValueError:
            raise naff.errors.BadArgument("Invalid summary given.") from None

        now = datetime.datetime.now(datetime.UTC)
        num_days_ago = (
            now - datetime.timedelta(days=num_days) + datetime.timedelta(minutes=1)
        )

        await self.process_graph(
            ctx,
            config=config,
            func_to_use=stats_utils.timespan_minutes_per_hour,
            now=now,
            min_datetime=num_days_ago,
            title=title.format(days_humanized=DAY_HUMANIZED[num_days]),
            bottom_label="Hour (UTC) in {localized_format}",
            localizations=(US_FORMAT_TIME, INTERNATIONAL_FORMAT_TIME),
            filter_kwargs=filter_kwargs,
            template_kwargs={"max_value": None},
        )

    premium = tansy.SlashCommand(
        name="premium",  # type: ignore
        description="Handles the configuration for Realms Playerlist Premium.",  # type: ignore
        default_member_permissions=naff.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @premium.subcommand(
        sub_cmd_name="graph-realm",
        sub_cmd_description=(
            "Produces a graph of the Realm's playtime over a specifed period as a"
            " graph. Beta, requires premium."
        ),
    )
    @naff.cooldown(naff.Buckets.GUILD, 1, 5)  # type: ignore
    @naff.check(stats_check)  # type: ignore
    async def graph_realm(
        self,
        ctx: utils.RealmContext,
        period: str = tansy.Option("The period to graph by.", choices=PERIOD_TO_GRAPH),  # type: ignore
    ) -> None:
        await self.process_unsummary(
            ctx, period, "Playtime on the Realm over the last {days_humanized}"
        )

    @premium.subcommand(
        sub_cmd_name="graph-realm-summary",
        sub_cmd_description=(
            "Summarizes the Realm over a specified period, by a specified interval."
            " Beta, requires premium."
        ),
    )
    @naff.cooldown(naff.Buckets.GUILD, 1, 5)  # type: ignore
    @naff.check(stats_check)  # type: ignore
    async def graph_realm_summary(
        self,
        ctx: utils.RealmContext,
        summarize_by: str = tansy.Option("What to summarize by.", choices=SUMMARIZE_BY),  # type: ignore
    ) -> None:
        await self.process_summary(
            ctx,
            summarize_by,
            "Summary of playtime on the Realm over the past {days_humanized} by hour",
        )

    @premium.subcommand(
        sub_cmd_name="graph-individual",
        sub_cmd_description=(
            "Produces a graph of a player's playtime over a specifed period as a"
            " graph. Beta, requires premium."
        ),
    )
    @naff.cooldown(naff.Buckets.GUILD, 1, 5)  # type: ignore
    @naff.check(stats_check)  # type: ignore
    async def graph_individual(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the user to graph."),
        period: str = tansy.Option("The period to graph by.", choices=PERIOD_TO_GRAPH),  # type: ignore
    ) -> None:
        xuid = await self.xuid_from_gamertag(gamertag)
        await self.process_unsummary(
            ctx,
            period,
            f"Playtime of {gamertag} over the last " + "{days_humanized}",
            indivdual=True,
            filter_kwargs={"xuid": xuid},
        )

    @premium.subcommand(
        sub_cmd_name="graph-individual-summary",
        sub_cmd_description=(
            "Summarizes a player over a specified period, by a specified interval."
            " Beta, requires premium."
        ),
    )
    @naff.cooldown(naff.Buckets.GUILD, 1, 5)  # type: ignore
    @naff.check(stats_check)  # type: ignore
    async def graph_individual_summary(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the user to graph."),
        summarize_by: str = tansy.Option("What to summarize by.", choices=SUMMARIZE_BY),  # type: ignore
    ) -> None:
        xuid = await self.xuid_from_gamertag(gamertag)
        await self.process_summary(
            ctx,
            summarize_by,
            f"Summary of playtime by {gamertag} over the past "
            + "{days_humanized} by hour",
            filter_kwargs={"xuid": xuid},
        )

    @tansy.slash_command(
        name="get-player-log",
        description="Gets a log of every time a specific player joined and left.",
        default_member_permissions=naff.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )  # type: ignore
    @naff.cooldown(naff.Buckets.GUILD, 1, 5)  # type: ignore
    async def get_player_log(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the user to get."),
        days_ago: int = tansy.Option(
            "How far the log should go (in days). Defaults to 1 day. Limit of 7 days.",
            min_value=1,
            max_value=7,
            default=1,
        ),
    ) -> None:
        """
        Gets a log of every time a specific player joined and left.

        Basically, the bot gathers up every time the player joined and left the Realm during \
        the timespan you specify and displays that to you.
        This information will only be gotten if the bot has been linked to the Realm for X \
        amount of days - otherwise, the best it is getting is partial data, likely to be \
        limited and slightly inaccurate.

        Has a cooldown of 5 seconds.
        """
        xuid = await self.xuid_from_gamertag(gamertag)

        config = await ctx.fetch_config()

        now = naff.Timestamp.utcnow().replace(second=30)
        time_delta = datetime.timedelta(days=days_ago, minutes=1)
        time_ago = now - time_delta

        sessions_str: list[str] = []

        async for session in models.PlayerSession.filter(
            Q(xuid=xuid)
            & Q(realm_id=config.realm_id)
            & Q(Q(online=True) | Q(last_seen__gte=time_ago))
        ).order_by("-last_seen"):
            session_str: list[str] = []

            if session.joined_at:
                session_str.append(
                    f"**Joined:** <t:{int(session.joined_at.timestamp())}:f>"
                )
            if session.online:
                session_str.append("**Currently Online**")
            elif session.last_seen:
                session_str.append(
                    f"**Left:** <t:{int(session.last_seen.timestamp())}:f>"
                )

            if not session_str:
                continue

            sessions_str.append("\n".join(session_str))

        if not sessions_str:
            raise utils.CustomCheckFailure(
                f"There is no data for `{gamertag}` for the last {days_ago} days on"
                " this Realm."
            )

        chunks = [sessions_str[x : x + 6] for x in range(0, len(sessions_str), 6)]
        # session number = (chunk index * 6) + (session-in-chunk index + 1) - () are added for clarity
        # why? well, say we're on the 3rd session chunk, and at the 5th entry for that chunk
        # the 3rd session chunk naturally means we have gone through (3 * 6) = 18 sessions beforehand,
        # so we know thats our minimum for this chunk
        # the session-in-chunk index is what we need to add to the "sessions beforehand" number
        # to get our original session str in the original list - we add one though because humans
        # don't index at 0
        embeds = [
            naff.Embed(
                f"Log for {gamertag} for the past {days_ago} days(s)",
                fields=[
                    naff.EmbedField(
                        f"Session {(chunk_index * 6) + (session_index + 1)}:",
                        session,
                        inline=True,
                    )
                    for session_index, session in enumerate(chunk)
                ],
                color=ctx.bot.color,
                footer=naff.EmbedFooter("As of"),
                timestamp=now,
            )
            for chunk_index, chunk in enumerate(chunks)
        ]

        if len(embeds) == 1:
            await ctx.send(embeds=embeds)
        else:
            # the help paginator looks better than the default imo
            pag = help_tools.HelpPaginator.create_from_embeds(
                ctx.bot, *embeds, timeout=60
            )
            pag.show_callback_button = False
            await pag.send(ctx)


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(stats_utils)
    importlib.reload(graph_template)
    importlib.reload(xbox_api)
    importlib.reload(help_tools)
    Statistics(bot)
