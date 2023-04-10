import asyncio
import contextlib
import datetime
import importlib
import os
import typing

import aiohttp
import humanize
import interactions as ipy
import orjson
import rapidfuzz
import tansy
from apischema import ValidationError
from tortoise.exceptions import DoesNotExist
from tortoise.expressions import Q

import common.fuzzy as fuzzy
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
DAY_OF_THE_WEEK = "%A"

SHOWABLE_FORMAT = {
    US_FORMAT_TIME: "HH AM/PM",
    US_FORMAT_DATE: "MM/DD/YY",
    US_FORMAT: "MM/DD/YY HH AM/PM",
    INTERNATIONAL_FORMAT_TIME: "HH:MM",
    INTERNATIONAL_FORMAT_DATE: "DD/MM/YY",
    INTERNATIONAL_FORMAT: "DD/MM/YY HH:MM",
    DAY_OF_THE_WEEK: "",  # no localization needed, here just so things don't fail
}

PERIOD_TO_GRAPH = [
    ipy.SlashCommandChoice("One day, per hour", "1pH"),
    ipy.SlashCommandChoice("1 week, per day", "7pD"),
]
PREMIUM_PERIOD_TO_GRAPH = PERIOD_TO_GRAPH + [
    ipy.SlashCommandChoice("2 weeks, per day", "14pD"),
    ipy.SlashCommandChoice("30 days, per day", "30pD"),
]
PERIODS = frozenset({p.value for p in PERIOD_TO_GRAPH})
PREMIUM_PERIODS = frozenset({p.value for p in PREMIUM_PERIOD_TO_GRAPH})

SUMMARIZE_BY = [
    ipy.SlashCommandChoice("1 week, by hour", "7bH"),
]
PREMIUM_SUMMARIZE_BY = SUMMARIZE_BY + [
    ipy.SlashCommandChoice("2 weeks, by hour", "14bH"),
    ipy.SlashCommandChoice("30 days, by hour", "30bH"),
    ipy.SlashCommandChoice("2 weeks, by day of the week", "14bD"),
    ipy.SlashCommandChoice("30 days, by day of the week", "30bD"),
]
SUMMARIES = frozenset({s.value for s in SUMMARIZE_BY})
PREMIUM_SUMMARIES = frozenset({s.value for s in PREMIUM_SUMMARIZE_BY})

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

    return bool(guild_config.realm_id)


class Statistics(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.name = "Statistics"

    async def xuid_from_gamertag(self, gamertag: str) -> str:
        maybe_xuid: typing.Union[str, xbox_api.ProfileResponse, None] = (
            await self.bot.redis.get(f"rpl-{gamertag}")
        )

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
            raise ipy.errors.BadArgument(f"`{gamertag}` is not a valid gamertag.")

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
            if not entry.joined_at or not entry.last_seen:
                continue

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
        warn_about_earliest: bool = False,
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

        embeds: list[ipy.Embed] = []

        if warn_about_earliest:
            # probably not the most elegant way to check if this is player-based or not
            # but it works for now
            if "Realm" in title:
                description = (
                    "The bot does not have enough data to properly graph data for the"
                    " timespan you specified (most likely, you specified a timespan"
                    " that goes further back than when you first set up the bot with"
                    " your Realm). This data may be inaccurate."
                )
            else:
                description = (
                    "The bot does not have enough data to properly graph data for the"
                    " timespan you specified (most likely, you specified a timespan"
                    " that goes further back than when you first set up the bot with"
                    " your Realm or when the player first started playing). This data"
                    " may be inaccurate."
                )
            embeds.append(
                ipy.Embed(
                    title="Warning",
                    description=description,
                    color=ipy.RoleColors.YELLOW,
                )
            )

        embed = ipy.Embed(
            color=self.bot.color,
            timestamp=now,  # type: ignore
        )
        embed.set_image(url)
        embeds.append(embed)

        await ctx.send(embeds=embeds)

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

        # if the minimum datetime plus one day that we passed is still before
        # the earliest datetime we've gathered, that probably means the bot
        # has only recently tracked a realm, and so we want to warn that
        # the data might not be the best
        earliest_datetime = min(d[0] for d in datetimes_to_use)
        warn_about_earliest = (
            min_datetime + datetime.timedelta(days=1) < earliest_datetime
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
            warn_about_earliest=warn_about_earliest,
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

        periods = PREMIUM_PERIODS if config.premium_code else PERIODS
        if period not in periods:
            raise ipy.errors.BadArgument("Invalid period given.")

        template_kwargs = {"max_value": None}

        period_split = period.split("p")
        if len(period_split) != 2:
            raise ipy.errors.BadArgument("Invalid period given.")

        try:
            num_days = int(period_split[0])
        except ValueError:
            raise ipy.errors.BadArgument("Invalid period given.") from None

        actual_period = period_split[1]

        now = datetime.datetime.now(datetime.UTC)
        num_days_ago = (
            now - datetime.timedelta(days=num_days) + datetime.timedelta(minutes=1)
        )

        if actual_period == "H":
            func_to_use = stats_utils.get_minutes_per_hour
            bottom_label = "Date and Hour (UTC) in {localized_format}"
            localizations = (US_FORMAT, INTERNATIONAL_FORMAT)

            num_days_ago = num_days_ago.replace(minute=0, second=0, microsecond=0)

            if indivdual:
                template_kwargs = {"max_value": 60}
        else:
            func_to_use = stats_utils.get_minutes_per_day
            bottom_label = "Date (UTC) in {localized_format}"
            localizations = (US_FORMAT_DATE, INTERNATIONAL_FORMAT_DATE)

            num_days_ago = num_days_ago.replace(
                hour=0, minute=0, second=0, microsecond=0
            )

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

        summaries = PREMIUM_SUMMARIES if config.premium_code else SUMMARIES
        if summarize_by not in summaries:
            raise ipy.errors.BadArgument("Invalid summary given.")

        summary_split = summarize_by.split("b")
        if len(summary_split) != 2:
            raise ipy.errors.BadArgument("Invalid summary given.")

        try:
            num_days = int(summary_split[0])
        except ValueError:
            raise ipy.errors.BadArgument("Invalid summary given.") from None

        now = datetime.datetime.now(datetime.UTC)
        num_days_ago = (
            now - datetime.timedelta(days=num_days) + datetime.timedelta(minutes=1)
        )

        actual_summarize_by = summary_split[1]

        if actual_summarize_by == "H":
            func_to_use = stats_utils.timespan_minutes_per_hour
            bottom_label = "Hour (UTC) in {localized_format}"
            localizations = (US_FORMAT_TIME, INTERNATIONAL_FORMAT_TIME)
            summarize_by_string = "hour"

        else:
            func_to_use = stats_utils.timespan_minutes_per_day_of_the_week
            bottom_label = "Day of the week (UTC)"
            localizations = (DAY_OF_THE_WEEK, DAY_OF_THE_WEEK)
            summarize_by_string = "day of the week"

        await self.process_graph(
            ctx,
            config=config,
            func_to_use=func_to_use,
            now=now,
            min_datetime=num_days_ago,
            title=title.format(
                days_humanized=DAY_HUMANIZED[num_days], summarize_by=summarize_by_string
            ),
            bottom_label=bottom_label,
            localizations=localizations,
            filter_kwargs=filter_kwargs,
            template_kwargs={"max_value": None},
        )

    graph = tansy.SlashCommand(
        name="graph",
        description="Produces various graphs about playtime on the Realm.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @graph.subcommand(
        sub_cmd_name="realm",
        sub_cmd_description=(
            "Produces a graph of the Realm's playtime over a specifed period as a"
            " graph."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    @ipy.check(stats_check)
    async def graph_realm(
        self,
        ctx: utils.RealmContext,
        period: str = tansy.Option("The period to graph by.", autocomplete=True),
    ) -> None:
        await self.process_unsummary(
            ctx, period, "Playtime on the Realm over the last {days_humanized}"
        )

    @graph.subcommand(
        sub_cmd_name="realm-summary",
        sub_cmd_description=(
            "Summarizes the Realm over a specified period, by a specified interval."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    @ipy.check(stats_check)
    async def graph_realm_summary(
        self,
        ctx: utils.RealmContext,
        summarize_by: str = tansy.Option("What to summarize by.", autocomplete=True),
    ) -> None:
        await self.process_summary(
            ctx,
            summarize_by,
            "Playtime on the Realm over the past {days_humanized} by {summarize_by}",
        )

    @graph.subcommand(
        sub_cmd_name="player",
        sub_cmd_description=(
            "Produces a graph of a player's playtime over a specifed period as a graph."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    @ipy.check(stats_check)
    async def graph_player(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the user to graph."),
        period: str = tansy.Option("The period to graph by.", autocomplete=True),
    ) -> None:
        xuid = await self.xuid_from_gamertag(gamertag)
        await self.process_unsummary(
            ctx,
            period,
            f"Playtime of {gamertag} over the last " + "{days_humanized}",
            indivdual=True,
            filter_kwargs={"xuid": xuid},
        )

    @graph.subcommand(
        sub_cmd_name="player-summary",
        sub_cmd_description=(
            "Summarizes a player over a specified period, by a specified interval."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    @ipy.check(stats_check)
    async def graph_player_summary(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the user to graph."),
        summarize_by: str = tansy.Option("What to summarize by.", autocomplete=True),
    ) -> None:
        xuid = await self.xuid_from_gamertag(gamertag)
        await self.process_summary(
            ctx,
            summarize_by,
            f"Playtime of {gamertag} over the past " + "{days_humanized} by hour",
            filter_kwargs={"xuid": xuid},
        )

    @staticmethod
    def _filter_for_fuzzy(period_summary: str | dict[str, typing.Any]) -> str:
        if isinstance(period_summary, str):
            return period_summary.lower()
        return period_summary["name"].lower()

    @graph_realm.autocomplete("period")
    @graph_player.autocomplete("period")
    async def period_autocomplete(
        self,
        ctx: utils.RealmAutocompleteContext,
        period: typing.Optional[str] = None,
        **kwargs: typing.Any,
    ) -> None:
        has_premium = await models.GuildConfig.exists(
            guild_id=ctx.guild.id, premium_code__id__not_isnull=True
        )
        periods = PREMIUM_PERIOD_TO_GRAPH if has_premium else PERIOD_TO_GRAPH
        periods_dict = [{"name": str(p.name), "value": p.value} for p in periods]

        if not period:
            await ctx.send(periods_dict)
            return

        filtered_periods = fuzzy.extract_from_list(
            period.lower(),
            periods_dict,
            (self._filter_for_fuzzy,),
            score_cutoff=80,
            scorers=(rapidfuzz.fuzz.WRatio,),
        )
        await ctx.send(p[0] for p in filtered_periods)

    @graph_realm_summary.autocomplete("summarize_by")
    @graph_player_summary.autocomplete("summarize_by")
    async def summary_autocomplete(
        self,
        ctx: utils.RealmAutocompleteContext,
        summarize_by: typing.Optional[str] = None,
        **kwargs: typing.Any,
    ) -> None:
        has_premium = await models.GuildConfig.exists(
            guild_id=ctx.guild.id, premium_code__id__not_isnull=True
        )
        summarize_bys = PREMIUM_SUMMARIZE_BY if has_premium else SUMMARIZE_BY
        summary_dict = [{"name": str(s.name), "value": s.value} for s in summarize_bys]

        if not summarize_by:
            await ctx.send(summary_dict)
            return

        filtered_summaries = fuzzy.extract_from_list(
            summarize_by.lower(),
            summary_dict,
            (self._filter_for_fuzzy,),
            score_cutoff=80,
            scorers=(rapidfuzz.fuzz.WRatio,),
        )
        await ctx.send(s[0] for s in filtered_summaries)

    @tansy.slash_command(
        name="get-player-log",
        description="Gets a log of every time a specific player joined and left.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
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

        now = ipy.Timestamp.utcnow().replace(second=30)
        time_delta = datetime.timedelta(days=days_ago, minutes=1)
        time_ago = now - time_delta

        sessions_str: list[str] = []
        total_playtime: float = 0.0

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

            if session.joined_at:
                last_seen = now if session.online else session.last_seen
                total_playtime += last_seen.timestamp() - session.joined_at.timestamp()

            sessions_str.append("\n".join(session_str))

        if not sessions_str:
            raise utils.CustomCheckFailure(
                f"There is no data for `{gamertag}` for the last {days_ago} days on"
                " this Realm."
            )

        natural_playtime = humanize.naturaldelta(total_playtime)

        chunks = [sessions_str[x : x + 6] for x in range(0, len(sessions_str), 6)]
        # session number = (chunk index * 6) + (session-in-chunk index + 1) - () are added for clarity
        # why? well, say we're on the 3rd session chunk, and at the 5th entry for that chunk
        # the 3rd session chunk naturally means we have gone through (3 * 6) = 18 sessions beforehand,
        # so we know thats our minimum for this chunk
        # the session-in-chunk index is what we need to add to the "sessions beforehand" number
        # to get our original session str in the original list - we add one though because humans
        # don't index at 0
        embeds = [
            ipy.Embed(
                title=f"Log for {gamertag} for the past {days_ago} days(s)",
                description=f"Total playtime over this period: {natural_playtime}",
                fields=[
                    ipy.EmbedField(
                        f"Session {(chunk_index * 6) + (session_index + 1)}:",
                        session,
                        inline=True,
                    )
                    for session_index, session in enumerate(chunk)
                ],
                color=ctx.bot.color,
                footer=ipy.EmbedFooter("As of"),
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
    importlib.reload(fuzzy)
    importlib.reload(stats_utils)
    importlib.reload(graph_template)
    importlib.reload(xbox_api)
    importlib.reload(help_tools)
    Statistics(bot)
