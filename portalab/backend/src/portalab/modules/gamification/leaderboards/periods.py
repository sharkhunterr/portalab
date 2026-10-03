"""Leaderboard periods (R13): ``all``, the current calendar ``month`` and ISO ``week`` (Monday), computed in
``economy.timezone`` and expressed as UTC instants."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from portalab.capabilities.economy import LeaderboardPeriod


def period_start(period: LeaderboardPeriod, now: datetime, timezone: str) -> datetime | None:
    if period == "all":
        return None
    try:
        zone = ZoneInfo(timezone)
    except (KeyError, ValueError):
        zone = ZoneInfo("UTC")
    local = now.astimezone(zone)
    day = local.replace(hour=0, minute=0, second=0, microsecond=0)
    start = day.replace(day=1) if period == "month" else day - timedelta(days=day.weekday())
    return start.replace(tzinfo=zone).astimezone(UTC)
