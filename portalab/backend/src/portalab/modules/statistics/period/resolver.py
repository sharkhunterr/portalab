"""``PeriodResolver`` (T012; R3): deterministic period boundaries over **daily buckets** in the single
statistics time zone with the configured first day of the week. Buckets are calendar days (DST changes the
length of a day, never its identity), so every consumer computes the same range for the same period."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from portalab.capabilities.statistics import Period
from portalab.core.errors import ValidationFailed

MAX_LAST_N_DAYS = 3660


class PeriodInvalid(ValidationFailed):
    default_code = "statistics.period_invalid"
    default_title = "Invalid period"


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def local_day(at: datetime, tz: ZoneInfo) -> date:
    """The statistics day an instant belongs to."""
    return at.astimezone(tz).date()


def _quarter_start(day: date) -> date:
    return date(day.year, 3 * ((day.month - 1) // 3) + 1, 1)


def _next_month(day: date) -> date:
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def resolve(period: Period, *, today: date, first_day_of_week: int = 0) -> tuple[date, date]:
    """``[start, end]`` inclusive days of ``period``; the anchor defaults to ``today``."""
    anchor = period.anchor or today
    match period.kind:
        case "day":
            return anchor, anchor
        case "week":
            start = anchor - timedelta(days=(anchor.weekday() - first_day_of_week) % 7)
            return start, start + timedelta(days=6)
        case "month":
            start = anchor.replace(day=1)
            return start, _next_month(start) - timedelta(days=1)
        case "quarter":
            start = _quarter_start(anchor)
            return start, _next_month(_next_month(_next_month(start))) - timedelta(days=1)
        case "year":
            return date(anchor.year, 1, 1), date(anchor.year, 12, 31)
        case "last_n_days":
            days = period.days if period.days is not None else 30
            if not 1 <= days <= MAX_LAST_N_DAYS:
                raise PeriodInvalid(f"last_n_days must be between 1 and {MAX_LAST_N_DAYS}.")
            return anchor - timedelta(days=days - 1), anchor
        case "custom":
            if period.start is None or period.end is None or period.end < period.start:
                raise PeriodInvalid("A custom period needs a start and an end after it.")
            return period.start, period.end
    raise PeriodInvalid(f"Unknown period {period.kind!r}.")


def previous(start: date, end: date) -> tuple[date, date]:
    """The preceding period of the same length (trend comparisons)."""
    length = (end - start).days + 1
    return start - timedelta(days=length), start - timedelta(days=1)


def parse_period(
    kind: str,
    *,
    days: int | None = None,
    start: str | None = None,
    end: str | None = None,
    anchor: str | None = None,
) -> Period:
    try:
        return Period(
            kind=kind,  # type: ignore[arg-type]
            days=days,
            start=date.fromisoformat(start) if start else None,
            end=date.fromisoformat(end) if end else None,
            anchor=date.fromisoformat(anchor) if anchor else None,
        )
    except ValueError as exc:
        raise PeriodInvalid("Dates are YYYY-MM-DD.") from exc
