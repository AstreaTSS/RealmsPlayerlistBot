import datetime
import io
import os
import typing
from collections import defaultdict
from enum import IntEnum

import interactions as ipy

import common.graph_template as graph_template
import common.models as models
import common.utils as utils

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
GATED_PERIOD_TO_GRAPH = PERIOD_TO_GRAPH + [
    ipy.SlashCommandChoice("2 weeks, per day", "14pD"),
    ipy.SlashCommandChoice("30 days, per day", "30pD"),
]
PERIODS = frozenset({p.value for p in PERIOD_TO_GRAPH})
GATED_PERIODS = frozenset({p.value for p in GATED_PERIOD_TO_GRAPH})

SUMMARIZE_BY = [
    ipy.SlashCommandChoice("1 week, by hour", "7bH"),
]
GATED_SUMMARIZE_BY = SUMMARIZE_BY + [
    ipy.SlashCommandChoice("2 weeks, by hour", "14bH"),
    ipy.SlashCommandChoice("30 days, by hour", "30bH"),
    ipy.SlashCommandChoice("2 weeks, by day of the week", "14bD"),
    ipy.SlashCommandChoice("30 days, by day of the week", "30bD"),
]
SUMMARIES = frozenset({s.value for s in SUMMARIZE_BY})
GATED_SUMMARIES = frozenset({s.value for s in GATED_SUMMARIZE_BY})

DAY_HUMANIZED = {
    1: "24 hours",
    7: "1 week",
    14: "2 weeks",
    30: "30 days",
}


class InSeconds(IntEnum):
    MINUTE = 60
    HOUR = MINUTE * 60
    DAY = HOUR * 24
    WEEK = DAY * 7
    MONTH = DAY * 30


def get_nearest_hour_timestamp(
    d: datetime.datetime,
) -> int:
    kwargs: dict[str, typing.Any] = {
        "minute": 0,
        "second": 0,
        "microsecond": 0,
        "tzinfo": datetime.UTC,
    }
    return int(d.replace(**kwargs).timestamp())


def get_nearest_day_timestamp(
    d: datetime.datetime,
) -> int:
    kwargs: dict[str, typing.Any] = {
        "hour": 0,
        "minute": 0,
        "second": 0,
        "microsecond": 0,
        "tzinfo": datetime.UTC,
    }
    return int(d.replace(**kwargs).timestamp())


class GatherDatetimesReturn(typing.NamedTuple):
    xuid: str
    joined_at: datetime.datetime
    last_seen: datetime.datetime


def get_minutes_per_hour(
    ranges: typing.Iterable[GatherDatetimesReturn],
    *,
    min_datetime: typing.Optional[datetime.datetime] = None,
    max_datetime: typing.Optional[datetime.datetime] = None,
) -> dict[datetime.datetime, int]:
    minutes_per_hour: defaultdict[int, int] = defaultdict(int)

    for _, start, end in ranges:
        end_time = int(end.timestamp())
        current_hour = int(start.timestamp())

        while current_hour < end_time:
            # comments arent repeated for every function, use this one as ref

            # you may be asking "what is hour floored?"
            # basically, it's the exact second the hour starts
            # so, say, instead of being 1:32:21, it'll be 1:00:00
            hour_floored = current_hour // InSeconds.HOUR * InSeconds.HOUR
            next_hour = hour_floored + InSeconds.HOUR

            # if the current hour + one hour is greater than the end time,
            # calculate the seconds between the end time and the current hour
            # else, calculate the seconds between the next hour and the current
            # hour time
            # note that we do not want to round current hour here or make assumptions
            # that it is floored as if it is, say, 1:32, and our end time is 1:54, we
            # want to make sure to calculate between 54 and 32, not 54 and 00
            minutes_in_hour = (
                (next_hour - current_hour) // 60
                if current_hour + InSeconds.HOUR <= end_time
                else (end_time - current_hour) // 60
            )

            minutes_per_hour[hour_floored] += minutes_in_hour
            current_hour = next_hour

    min_timestamp = (
        get_nearest_hour_timestamp(min_datetime)
        if min_datetime
        else min(minutes_per_hour.keys())
    )
    max_timestamp = (
        get_nearest_hour_timestamp(max_datetime)
        if max_datetime
        else max(minutes_per_hour.keys())
    )

    return {
        datetime.datetime.utcfromtimestamp(k): minutes_per_hour[k]
        for k in range(min_timestamp, max_timestamp + 1, InSeconds.HOUR)
    }


def get_minutes_per_day(
    ranges: typing.Iterable[GatherDatetimesReturn],
    *,
    min_datetime: typing.Optional[datetime.datetime] = None,
    max_datetime: typing.Optional[datetime.datetime] = None,
) -> dict[datetime.datetime, int]:
    minutes_per_day: defaultdict[int, int] = defaultdict(int)

    for _, start, end in ranges:
        end_time = int(end.timestamp())
        current_day = int(start.timestamp())

        while current_day < end_time:
            day_floored = current_day // InSeconds.DAY * InSeconds.DAY
            next_day = day_floored + InSeconds.DAY

            minutes_in_day = (
                (next_day - current_day) // 60
                if current_day + InSeconds.DAY <= end_time
                else (end_time - current_day) // 60
            )

            minutes_per_day[day_floored] += minutes_in_day
            current_day = next_day

    min_timestamp = (
        get_nearest_day_timestamp(min_datetime)
        if min_datetime
        else min(minutes_per_day.keys())
    )
    max_timestamp = (
        get_nearest_day_timestamp(max_datetime)
        if max_datetime
        else max(minutes_per_day.keys())
    )

    return {
        datetime.datetime.utcfromtimestamp(k): minutes_per_day[k]
        for k in range(min_timestamp, max_timestamp + 1, InSeconds.DAY)
    }


def timespan_minutes_per_hour(
    ranges: typing.Iterable[GatherDatetimesReturn],
    **kwargs: typing.Any,
) -> dict[datetime.time, int]:
    # we want the dict to start at 0, so make the dict first
    minutes_per_hour: dict[int, int] = {i: 0 for i in range(24)}

    for _, start, end in ranges:
        end_time = int(end.timestamp())
        current_hour = int(start.timestamp())

        while current_hour < end_time:
            next_hour = (
                current_hour // InSeconds.HOUR * InSeconds.HOUR
            ) + InSeconds.HOUR

            minutes_in_hour = (
                (next_hour - current_hour) // 60
                if current_hour + InSeconds.HOUR <= end_time
                else (end_time - current_hour) // 60
            )

            # represents the hour of the day the time is in
            minutes_per_hour[
                current_hour % InSeconds.DAY // InSeconds.HOUR
            ] += minutes_in_hour
            current_hour = next_hour

    return {datetime.time(hour=k): v for k, v in minutes_per_hour.items()}


def timespan_minutes_per_day_of_the_week(
    ranges: typing.Iterable[GatherDatetimesReturn],
    **kwargs: typing.Any,
) -> dict[datetime.date, int]:
    minutes_per_day_of_the_week: dict[int, int] = {i: 0 for i in range(7)}

    for _, start, end in ranges:
        end_time = int(end.timestamp())
        current_day = int(start.timestamp())

        while current_day < end_time:
            next_day = (current_day // InSeconds.DAY * InSeconds.DAY) + InSeconds.DAY
            minutes_in_day = (
                (next_day - current_day) // 60
                if current_day + InSeconds.DAY <= end_time
                else (end_time - current_day) // 60
            )

            # https://stackoverflow.com/questions/36389130/how-to-calculate-the-day-of-the-week-based-on-unix-time
            minutes_per_day_of_the_week[
                ((current_day // InSeconds.DAY) + 4) % 7
            ] += minutes_in_day
            current_day = next_day

    return {
        datetime.date(year=1970, month=1, day=(k - 3) + 7): v
        for k, v in minutes_per_day_of_the_week.items()
    }


async def gather_datetimes(
    config: models.GuildConfig,
    min_datetime: datetime.datetime,
    *,
    gamertag: typing.Optional[str] = None,
    **filter_kwargs: typing.Any,
) -> list[GatherDatetimesReturn]:
    datetimes_to_use: list[GatherDatetimesReturn] = []

    async for entry in models.PlayerSession.filter(
        realm_id=config.realm_id, joined_at__gte=min_datetime, **filter_kwargs
    ):
        if not entry.joined_at or not entry.last_seen:
            continue

        datetimes_to_use.append(
            GatherDatetimesReturn(entry.xuid, entry.joined_at, entry.last_seen)
        )

    if not datetimes_to_use:
        if gamertag:
            raise utils.CustomCheckFailure(
                f"There's no data for `{gamertag}` on the linked Realm for this"
                " timespan."
            )
        else:
            raise utils.CustomCheckFailure(
                "There's no data for the linked Realm for this timespan."
            )

    return datetimes_to_use


async def period_parse(
    bot: utils.RealmBotBase,
    user_id: ipy.Snowflake_Type,
    config: models.GuildConfig,
    period: str,
) -> tuple[int, str]:
    if period not in PERIODS:
        if period in GATED_PERIODS:
            if (
                os.environ.get("TOP_GG_TOKEN")
                and not config.valid_premium
                and await bot.redis.get(f"rpl-voted-{user_id}") != "1"
            ):
                raise utils.CustomCheckFailure(
                    "To use periods longer than 1 week, you must vote for the bot [on"
                    f" its Top.gg page](https://top.gg/bot/{bot.user.id}/vote) or"
                    " [purchase Playerlist"
                    f" Premium]({os.environ['PREMIUM_INFO_LINK']}). Voting lasts for 12"
                    " hours."
                )
        else:
            raise ipy.errors.BadArgument("Invalid period given.")

    period_split = period.split("p")
    if len(period_split) != 2:
        raise ipy.errors.BadArgument("Invalid period given.")

    try:
        num_days = int(period_split[0])
    except ValueError:
        raise ipy.errors.BadArgument("Invalid period given.") from None

    return num_days, period_split[1]


async def summary_parse(
    bot: utils.RealmBotBase,
    user_id: ipy.Snowflake_Type,
    config: models.GuildConfig,
    summarize_by: str,
) -> tuple[int, str]:
    if summarize_by not in SUMMARIES:
        if summarize_by in GATED_SUMMARIES:
            if (
                os.environ.get("TOP_GG_TOKEN")
                and not config.valid_premium
                and await bot.redis.get(f"rpl-voted-{user_id}") != "1"
            ):
                raise utils.CustomCheckFailure(
                    "To use periods longer than 1 week, you must vote for the bot [on"
                    f" its Top.gg page](https://top.gg/bot/{bot.user.id}/vote) or"
                    " [purchase Playerlist"
                    f" Premium]({os.environ['PREMIUM_INFO_LINK']}). Voting lasts for 12"
                    " hours."
                )
        else:
            raise ipy.errors.BadArgument("Invalid summary given.")

    summary_split = summarize_by.split("b")
    if len(summary_split) != 2:
        raise ipy.errors.BadArgument("Invalid summary given.")

    try:
        num_days = int(summary_split[0])
    except ValueError:
        raise ipy.errors.BadArgument("Invalid summary given.") from None

    return num_days, summary_split[1]


class ProcessUnsummaryReturn(typing.NamedTuple):
    func_to_use: typing.Callable[..., VALID_TIME_DICTS]
    bottom_label: str
    localizations: tuple[str, ...]
    min_datetime: datetime.datetime
    formatted_title: str
    template_kwargs: dict[str, typing.Any]


class ProcessSummaryReturn(typing.NamedTuple):
    func_to_use: typing.Callable[..., VALID_TIME_DICTS]
    bottom_label: str
    localizations: tuple[str, ...]
    formatted_title: str
    min_datetime: datetime.datetime


async def process_unsummary(
    ctx: utils.RealmContext | utils.RealmModalContext,
    now: datetime.datetime,
    period: str,
    title: str,
    *,
    indivdual: bool = False,
) -> ProcessUnsummaryReturn:
    config = await ctx.fetch_config()
    template_kwargs = {"max_value": None}

    num_days, actual_period = await period_parse(ctx.bot, ctx.author_id, config, period)
    min_datetime = (
        now - datetime.timedelta(days=num_days) + datetime.timedelta(minutes=1)
    )

    if actual_period == "H":
        func_to_use = get_minutes_per_hour
        bottom_label = "Date and Hour (UTC) in {localized_format}"
        localizations = (US_FORMAT, INTERNATIONAL_FORMAT)

        min_datetime = min_datetime.replace(minute=0, second=0, microsecond=0)

        if indivdual:
            template_kwargs = {"max_value": 60}
    else:
        func_to_use = get_minutes_per_day
        bottom_label = "Date (UTC) in {localized_format}"
        localizations = (US_FORMAT_DATE, INTERNATIONAL_FORMAT_DATE)

        min_datetime = min_datetime.replace(hour=0, minute=0, second=0, microsecond=0)

    return ProcessUnsummaryReturn(
        func_to_use,
        bottom_label,
        localizations,
        min_datetime,
        title.format(days_humanized=DAY_HUMANIZED[num_days]),
        template_kwargs,
    )


async def process_summary(
    ctx: utils.RealmContext | utils.RealmModalContext,
    now: datetime.datetime,
    summarize_by: str,
    title: str,
) -> ProcessSummaryReturn:
    config = await ctx.fetch_config()

    num_days, actual_summarize_by = await summary_parse(
        ctx.bot, ctx.author_id, config, summarize_by
    )
    min_datetime = (
        now - datetime.timedelta(days=num_days) + datetime.timedelta(minutes=1)
    )

    if actual_summarize_by == "H":
        func_to_use = timespan_minutes_per_hour
        bottom_label = "Hour (UTC) in {localized_format}"
        localizations = (US_FORMAT_TIME, INTERNATIONAL_FORMAT_TIME)
        summarize_by_string = "hour"

    else:
        func_to_use = timespan_minutes_per_day_of_the_week
        bottom_label = "Day of the week (UTC)"
        localizations = (DAY_OF_THE_WEEK, DAY_OF_THE_WEEK)
        summarize_by_string = "day of the week"

    return ProcessSummaryReturn(
        func_to_use,
        bottom_label,
        localizations,
        title.format(
            days_humanized=DAY_HUMANIZED[num_days], summarize_by=summarize_by_string
        ),
        min_datetime,
    )


async def process_single_graph_data(
    config: models.GuildConfig,
    *,
    min_datetime: datetime.datetime,
    now: datetime.datetime,
    func_to_use: typing.Callable[..., VALID_TIME_DICTS],
    gamertag: typing.Optional[str] = None,
    filter_kwargs: typing.Optional[dict[str, typing.Any]] = None,
) -> tuple[VALID_TIME_DICTS, list[GatherDatetimesReturn]]:
    if filter_kwargs is None:
        filter_kwargs = {}

    datetimes_to_use = await gather_datetimes(
        config, min_datetime, gamertag=gamertag, **filter_kwargs
    )

    return (
        func_to_use(
            datetimes_to_use,
            min_datetime=min_datetime,
            max_datetime=now,
        ),
        datetimes_to_use,
    )


async def process_multi_graph_data(
    config: models.GuildConfig,
    xuid_list: list[str],
    *,
    gamertag_list: list[str],
    min_datetime: datetime.datetime,
    now: datetime.datetime,
    func_to_use: typing.Callable[..., VALID_TIME_DICTS],
) -> tuple[dict[str, VALID_TIME_DICTS], datetime.datetime]:
    xuid_datetime_map: dict[str, list[GatherDatetimesReturn]] = {}

    for xuid, gamertag in zip(xuid_list, gamertag_list, strict=True):
        xuid_datetime_map[xuid] = await gather_datetimes(
            config, min_datetime, gamertag=gamertag, xuid=xuid
        )

    earliest_datetime = min(
        d.last_seen
        for d in (
            entry
            for datetime_lists in xuid_datetime_map.values()
            for entry in datetime_lists
        )
    )

    minutes_per_period_map = {
        xuid: func_to_use(datetimes_to_use, min_datetime=min_datetime, max_datetime=now)
        for xuid, datetimes_to_use in xuid_datetime_map.items()
    }

    return minutes_per_period_map, earliest_datetime


def create_single_graph(
    ctx: utils.RealmContext,
    *,
    title: str,
    bottom_label: str,
    time_data: VALID_TIME_DICTS,
    localizations: tuple[str, str],
    **template_kwargs: typing.Any,
) -> str | dict[str, typing.Any]:
    locale = ctx.locale or ctx.guild_locale or "en_GB"
    # im aware theres countries that do yy/mm/dd - i'll add them in soon
    locale_to_use = localizations[0] if locale == "en-US" else localizations[1]

    localized = {k.strftime(locale_to_use): v for k, v in time_data.items()}
    url = graph_template.graph_template(
        title,
        "Total Minutes Played",
        bottom_label.format(localized_format=SHOWABLE_FORMAT[locale_to_use]),
        tuple(localized.keys()),
        tuple(localized.values()),
        **template_kwargs,
    )

    # discord doesn't like this, return dict so we can make post req later
    if len(url) > 2048:
        return graph_template.graph_dict(
            title,
            "Total Minutes Played",
            bottom_label.format(localized_format=SHOWABLE_FORMAT[locale_to_use]),
            tuple(localized.keys()),
            tuple(localized.values()),
            **template_kwargs,
        )
    return url


def create_multi_graph(
    ctx: utils.RealmContext | utils.RealmModalContext,
    *,
    title: str,
    bottom_label: str,
    time_data: dict[str, VALID_TIME_DICTS],
    gamertags: list[str],
    localizations: tuple[str, str],
    **template_kwargs: typing.Any,
) -> str | dict[str, typing.Any]:
    first_xuid: str = next(iter(time_data.keys()))

    locale = ctx.locale or ctx.guild_locale or "en_GB"
    # im aware theres countries that do yy/mm/dd - i'll add them in soon
    locale_to_use = localizations[0] if locale == "en-US" else localizations[1]

    localized_keys = tuple(v.strftime(locale_to_use) for v in time_data[first_xuid])
    data_points = tuple(tuple(v.values()) for v in time_data.values())

    url = graph_template.multi_graph_template(
        title,
        "Total Minutes Played",
        bottom_label.format(localized_format=SHOWABLE_FORMAT[locale_to_use]),
        localized_keys,
        tuple(gamertags),
        data_points,
        **template_kwargs,
    )
    if len(url) > 2048:
        return graph_template.multi_graph_dict(
            title,
            "Total Minutes Played",
            bottom_label.format(localized_format=SHOWABLE_FORMAT[locale_to_use]),
            localized_keys,
            tuple(gamertags),
            data_points,
            **template_kwargs,
        )
    return url


async def send_graph(
    ctx: utils.RealmContext | utils.RealmModalContext,
    *,
    graph: str | dict[str, typing.Any],
    now: datetime.datetime,
    title: str,
    min_datetime: datetime.datetime,
    datetimes_used: typing.Optional[list[GatherDatetimesReturn]] = None,
    earliest_datetime: typing.Optional[datetime.datetime] = None,
) -> None:
    kwargs: dict[str, typing.Any] = {}

    try:
        if isinstance(graph, dict):
            payload = {
                "bkg": "white",
                "w": 700,
                "h": 400,
                "chart": graph,
            }
            async with ctx.bot.session.post(
                "https://quickchart.io/chart", json=payload
            ) as resp:
                resp.raise_for_status()
                file = ipy.File(io.BytesIO(await resp.read()), file_name="graph.png")
                kwargs["file"] = file

        if not earliest_datetime:
            # if the minimum datetime plus one day that we passed is still before
            # the earliest datetime we've gathered, that probably means the bot
            # has only recently tracked a realm, and so we want to warn that
            # the data might not be the best
            earliest_datetime = min(d.last_seen for d in datetimes_used)  # type: ignore

        warn_about_earliest = (
            min_datetime + datetime.timedelta(days=1) < earliest_datetime
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
            elif "various players" in title:
                description = (
                    "The bot does not have enough data to properly graph data for the"
                    " timespan you specified (most likely, you specified a timespan"
                    " that goes further back than when you first set up the bot with"
                    " your Realm or when the oldest player first started playing). This"
                    " data may be inaccurate."
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
            color=ctx.bot.color,
            timestamp=now,  # type: ignore
        )
        embed.set_image(graph if isinstance(graph, str) else "attachment://graph.png")

        embeds.append(embed)
        kwargs["embeds"] = embeds

        await ctx.send(**kwargs)
    finally:
        if kwargs.get("file") and isinstance(
            kwargs["file"].file, io.IOBase | typing.BinaryIO
        ):
            kwargs["file"].file.close()
