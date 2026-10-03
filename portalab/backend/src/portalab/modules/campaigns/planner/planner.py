"""Occurrence planner (T010; R3): expands a schedule into concrete UTC windows. Times are wall-clock in the
campaign's time zone and resolved through the 026 policy (DST gap → forward, overlap → earlier); yearly
anchors on Feb 29 fall back to Feb 28; monthly anchors past the month end clamp to its last day. The output
is deterministic."""

import calendar
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from portalab.modules.campaigns.definitions.schema import CampaignDefinition

Resolve = Callable[[datetime, str], datetime]


def resolve_wall_clock(local: datetime, time_zone: str) -> datetime:
    """Fallback of 026's ``resolve_wall_clock`` (policy ``gap_forward|overlap_earlier``)."""
    tz = ZoneInfo(time_zone)
    naive = local.replace(tzinfo=None)
    early = naive.replace(tzinfo=tz, fold=0)
    late = naive.replace(tzinfo=tz, fold=1)
    if early.utcoffset() == late.utcoffset():
        return early.astimezone(UTC)
    in_gap = early.astimezone(UTC).astimezone(tz).replace(tzinfo=None) != naive
    if in_gap:
        shift = abs((late.utcoffset() or timedelta(0)) - (early.utcoffset() or timedelta(0)))
        return (naive + shift).replace(tzinfo=tz).astimezone(UTC)
    return early.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class Window:
    index: int
    start_at: datetime
    end_at: datetime


def _add_months(moment: datetime, months: int, anchor_day: int) -> datetime:
    month = moment.month - 1 + months
    year, month = moment.year + month // 12, month % 12 + 1
    day = min(anchor_day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def _year(moment: datetime, year: int) -> datetime:
    if moment.month == 2 and moment.day == 29 and not calendar.isleap(year):
        return moment.replace(year=year, day=28)
    return moment.replace(year=year)


def local_starts(definition: CampaignDefinition) -> list[datetime]:
    schedule = definition.schedule
    first = schedule.start_at
    recurrence = schedule.recurrence
    if recurrence.kind == "none":
        return [first]
    if recurrence.kind == "yearly":
        return [_year(first, first.year + n) for n in range(recurrence.count)]
    starts = []
    for n in range(recurrence.count):
        step = n * recurrence.every
        if recurrence.unit == "days":
            starts.append(first + timedelta(days=step))
        elif recurrence.unit == "weeks":
            starts.append(first + timedelta(weeks=step))
        else:
            starts.append(_add_months(first, step, first.day))
    return starts


def expand(definition: CampaignDefinition, resolve: Resolve = resolve_wall_clock) -> list[Window]:
    schedule = definition.schedule
    length = (
        schedule.end_at - schedule.start_at
        if schedule.end_at is not None
        else timedelta(hours=schedule.duration_hours or 1)
    )
    windows = []
    for index, start in enumerate(local_starts(definition)):
        start_utc = resolve(start, definition.timezone)
        end_utc = resolve(start + length, definition.timezone)
        if end_utc > start_utc:
            windows.append(Window(index, start_utc, end_utc))
    return windows
