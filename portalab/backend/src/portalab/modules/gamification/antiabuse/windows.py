"""Usage windows (T022; R7): windows are keyed from an event's ``occurred_at`` in the economy time zone, so
a late event is judged by the window it belongs to."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = ZoneInfo("UTC")


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


def window_start(kind: str, at: datetime, tz: str) -> datetime:
    local = at.astimezone(zone(tz))
    if kind == "hour":
        start = local.replace(minute=0, second=0, microsecond=0)
    elif kind == "day":
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    elif kind == "week":
        start = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f"unknown window {kind!r}")
    return start.astimezone(UTC)
