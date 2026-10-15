"""Leaderboard periods (R13, #128): ``all``, the current ISO ``week`` (from Monday), calendar ``month``,
the last ``6months`` (this month and the five before), this calendar ``year`` and the last ``3years`` (this
year and the two before) — computed in ``economy.timezone`` and expressed as UTC instants. Each starts on a
day boundary, so a board stays the same board until its period turns."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from portalab.capabilities.economy import LeaderboardPeriod


def _months_back(day: datetime, months: int) -> datetime:
    index = day.year * 12 + day.month - 1 - months
    return day.replace(year=index // 12, month=index % 12 + 1, day=1)


def period_start(period: LeaderboardPeriod, now: datetime, timezone: str) -> datetime | None:
    if period == "all":
        return None
    try:
        zone = ZoneInfo(timezone)
    except (KeyError, ValueError):
        zone = ZoneInfo("UTC")
    local = now.astimezone(zone)
    day = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        start = day - timedelta(days=day.weekday())
    elif period == "month":
        start = day.replace(day=1)
    elif period == "6months":
        start = _months_back(day, 5)
    elif period == "year":
        start = day.replace(month=1, day=1)
    else:  # 3years
        start = day.replace(year=day.year - 2, month=1, day=1)
    return start.replace(tzinfo=zone).astimezone(UTC)
