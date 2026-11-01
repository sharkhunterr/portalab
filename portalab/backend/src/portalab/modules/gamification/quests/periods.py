"""Quest period keys (R11): computed in ``economy.timezone`` from the event's ``occurred_at``, so replays
and late events land in the period they happened in (DST-safe: local calendar dates, not 24-hour slices)."""

from datetime import date, datetime, time, timedelta
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


def period_end(period: Period, at: datetime, timezone: str) -> datetime | None:
    """#307: when the period holding ``at`` ends — the next local midnight, Monday or first of the month
    (when a daily, weekly or monthly objective starts again); ``None`` for a quest done once."""
    if period == "none":
        return None
    zone = _zone(timezone)
    day = at.astimezone(zone).date()
    if period == "day":
        following = day + timedelta(days=1)
    elif period == "week":
        following = day + timedelta(days=7 - day.weekday())
    else:
        following = date(day.year + day.month // 12, day.month % 12 + 1, 1)
    return datetime.combine(following, time(), zone)
