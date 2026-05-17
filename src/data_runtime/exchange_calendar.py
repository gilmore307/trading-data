"""Small reviewed exchange-calendar helper for US equity source timing.

This is intentionally narrow: it only provides the next regular NYSE session
open needed for point-in-time ETF-holdings availability. It does not model early
closes or intraday trading sessions.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def next_regular_us_equity_open_after(as_of_date: date | str) -> str:
    day = _coerce_date(as_of_date) + timedelta(days=1)
    while not is_regular_us_equity_session(day):
        day += timedelta(days=1)
    return datetime(day.year, day.month, day.day, 9, 30, tzinfo=ET).isoformat()


def is_regular_us_equity_session(day: date) -> bool:
    return day.weekday() < 5 and day not in us_equity_holidays(day.year)


def us_equity_holidays(year: int) -> set[date]:
    holidays = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday / Presidents Day
        _easter_sunday(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial Day
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed(date(year, 12, 25)),
    }
    if year >= 2022:
        holidays.add(_observed(date(year, 6, 19)))
    return holidays


def _coerce_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    day = date(year, month, 1)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day + timedelta(days=7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    day = date(year + (month // 12), (month % 12) + 1, 1) - timedelta(days=1)
    while day.weekday() != weekday:
        day -= timedelta(days=1)
    return day


def _easter_sunday(year: int) -> date:
    # Anonymous Gregorian algorithm.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


__all__ = ["is_regular_us_equity_session", "next_regular_us_equity_open_after", "us_equity_holidays"]
