"""Time zones, wall-clock schedules and DST (T023; R5, FR-008..010).

Instants are stored in UTC and rendered in the viewer's zone. A *wall-clock* intent ("every day at 02:30
Paris time") is resolved to an absolute instant per occurrence: a local time inside a DST **gap** moves
forward (or backward) by the gap, one inside an **overlap** takes the earlier (or later) instant — per
``i18n.ambiguousTimePolicy`` — and never raises. ``next_occurrence`` serves 014/019 schedules in
``absolute`` or ``wall_clock`` mode without double-firing or skipping across transitions.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from portalab.capabilities.i18n import LocaleContext
from portalab.modules.i18n.format.formatter import Formatter

DEFAULT_POLICY = "gap_forward|overlap_earlier"


def zone(name: str, fallback: str = "UTC") -> tuple[ZoneInfo, bool]:
    """The zone, and whether it was the requested one (unknown zones fall back and are flagged)."""
    try:
        return ZoneInfo(name), True
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(fallback), False


def resolve_wall_clock(local: datetime, time_zone: str, policy: str | None = None) -> datetime:
    gap_rule, _, overlap_rule = (policy or DEFAULT_POLICY).partition("|")
    tz, _ = zone(time_zone)
    naive = local.replace(tzinfo=None)
    early = naive.replace(tzinfo=tz, fold=0)
    late = naive.replace(tzinfo=tz, fold=1)
    if early.utcoffset() == late.utcoffset():
        return early.astimezone(UTC)
    # Round-tripping tells a gap (the wall time does not exist) from an overlap (it exists twice).
    in_gap = early.astimezone(UTC).astimezone(tz).replace(tzinfo=None) != naive
    if in_gap:
        offset_early, offset_late = early.utcoffset() or timedelta(0), late.utcoffset() or timedelta(0)
        shift = abs(offset_late - offset_early)
        target = naive + shift if gap_rule == "gap_forward" else naive - shift
        return target.replace(tzinfo=tz).astimezone(UTC)
    chosen = late if overlap_rule == "overlap_later" else early
    return chosen.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class Schedule:
    mode: Literal["absolute", "wall_clock"]
    every: timedelta = timedelta(days=1)
    at: time | None = None  # wall-clock time of day (wall_clock mode)
    time_zone: str = "UTC"  # reference zone of the intent (stored with the schedule)
    anchor: datetime | None = None  # first absolute instant (absolute mode)


def next_occurrence(schedule: Schedule, after: datetime, policy: str | None = None) -> datetime:
    after = after.astimezone(UTC)
    if schedule.mode == "absolute":
        anchor = (schedule.anchor or after).astimezone(UTC)
        if anchor > after:
            return anchor
        steps = int((after - anchor) / schedule.every) + 1
        return anchor + steps * schedule.every
    tz, _ = zone(schedule.time_zone)
    at = schedule.at or time(0, 0)
    local_day = after.astimezone(tz).date()
    for offset in range(3):
        candidate = resolve_wall_clock(
            datetime.combine(local_day + timedelta(days=offset), at), schedule.time_zone, policy
        )
        if candidate > after:
            return candidate
    raise RuntimeError("unreachable")


class TimeRenderer:
    def __init__(self, formatter: Formatter | None = None) -> None:
        self.formatter = formatter or Formatter()

    def render_instant(self, instant: datetime, ctx: LocaleContext, style: str = "medium") -> str:
        return self.formatter.datetime(instant, ctx, style)

    def resolve_wall_clock(self, local: datetime, time_zone: str, policy: str | None = None) -> datetime:
        return resolve_wall_clock(local, time_zone, policy)
