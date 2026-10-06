"""Quest period keys (R11): computed in ``economy.timezone`` from the event's ``occurred_at``, so replays
and late events land in the period they happened in (DST-safe: local calendar dates, not 24-hour slices)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from portalab.modules.gamification.quests.definition import Period


def _zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except (KeyError, ValueError):
        return ZoneInfo("UTC")


def period_key(period: Period, at: datetime, timezone: str) -> str:
    if period == "none":
        return "once"
    local = at.astimezone(_zone(timezone))
    if period == "day":
        return local.date().isoformat()
    if period == "month":  # 027: monthly objectives
        return f"{local.year}-M{local.month:02d}"
    year, week, _ = local.isocalendar()
    return f"{year}-W{week:02d}"
