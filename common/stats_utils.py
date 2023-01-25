import datetime
import typing
from collections import defaultdict
from enum import IntEnum


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


def get_minutes_per_hour(
    ranges: typing.Iterable[tuple[datetime.datetime, datetime.datetime]],
    *,
    min_datetime: typing.Optional[datetime.datetime] = None,
    max_datetime: typing.Optional[datetime.datetime] = None,
) -> dict[datetime.datetime, int]:
    minutes_per_hour: defaultdict[int, int] = defaultdict(int)

    for start, end in ranges:
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
    ranges: typing.Iterable[tuple[datetime.datetime, datetime.datetime]],
    *,
    min_datetime: typing.Optional[datetime.datetime] = None,
    max_datetime: typing.Optional[datetime.datetime] = None,
) -> dict[datetime.datetime, int]:
    minutes_per_day: defaultdict[int, int] = defaultdict(int)

    for start, end in ranges:
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
    ranges: typing.Iterable[tuple[datetime.datetime, datetime.datetime]],
    **kwargs: typing.Any,
) -> dict[datetime.time, int]:
    # we want the dict to start at 0, so make the dict first
    minutes_per_hour: dict[int, int] = {i: 0 for i in range(24)}

    for start, end in ranges:
        end_time = int(end.timestamp())
        current_hour = int(start.timestamp())

        while current_hour < end_time:
            next_hour = (
                current_hour % InSeconds.HOUR // InSeconds.HOUR
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
