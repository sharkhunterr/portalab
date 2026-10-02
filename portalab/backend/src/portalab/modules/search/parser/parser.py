"""``QueryParser`` (T009; R7, R13): free text + typed filters (``type:services``, ``state:enabled``,
``after:2026-01-01``, ``date:this-week``) + natural relative dates ("this week", "recently", "cette
semaine"…) resolved in the user's time zone and first day of the week (026). The text is length-capped and
only ever bound as a parameter (``websearch_to_tsquery`` parses operators); filter names and values are
validated, never interpolated."""

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from portalab.capabilities.i18n import LocaleContext, normalize_for_search
from portalab.capabilities.search import Mode, ParsedQuery
from portalab.core.errors import ValidationFailed

FILTER_TOKEN = re.compile(r"(?<!\S)([a-z][a-z0-9_]{0,31}):(\"[^\"]{1,64}\"|[^\s\"]{1,64})(?!\S)")
FILTER_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
TYPE_FILTERS = frozenset({"type", "kind"})
DATE_FILTERS = frozenset({"date", "after", "before"})
MAX_FILTERS = 10
MAX_VALUES = 10
RECENT_DAYS = 14

RELATIVE: Mapping[str, str] = {
    # English
    "today": "today",
    "yesterday": "yesterday",
    "this week": "this-week",
    "last week": "last-week",
    "this month": "this-month",
    "last month": "last-month",
    "recently": "recently",
    "recent": "recently",
    # French
    "aujourd'hui": "today",
    "hier": "yesterday",
    "cette semaine": "this-week",
    "la semaine derniere": "last-week",
    "semaine derniere": "last-week",
    "ce mois-ci": "this-month",
    "ce mois": "this-month",
    "le mois dernier": "last-month",
    "recemment": "recently",
}
_PHRASES = sorted(RELATIVE, key=len, reverse=True)


class QueryTooLong(ValidationFailed):
    default_code = "search.query_too_long"
    default_title = "Search query too long"


class InvalidFilter(ValidationFailed):
    default_code = "search.invalid_filter"
    default_title = "Invalid search filter"


def _zone(ctx: LocaleContext) -> ZoneInfo:
    try:
        return ZoneInfo(ctx.time_zone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def relative_range(name: str, ctx: LocaleContext, now: datetime) -> tuple[datetime, datetime] | None:
    """``[from, to)`` in UTC for a relative date name, computed on the user's local calendar."""
    zone = _zone(ctx)
    today = now.astimezone(zone).date()

    def at(day: date) -> datetime:
        return datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)

    first_day = ctx.first_day_of_week if ctx.first_day_of_week is not None else 0  # 0 = Monday
    week_start = today - timedelta(days=(today.weekday() - first_day) % 7)
    month_start = today.replace(day=1)
    match name:
        case "today":
            return at(today), at(today + timedelta(days=1))
        case "yesterday":
            return at(today - timedelta(days=1)), at(today)
        case "this-week":
            return at(week_start), at(week_start + timedelta(days=7))
        case "last-week":
            return at(week_start - timedelta(days=7)), at(week_start)
        case "this-month":
            next_month = (month_start + timedelta(days=32)).replace(day=1)
            return at(month_start), at(next_month)
        case "last-month":
            previous = (month_start - timedelta(days=1)).replace(day=1)
            return at(previous), at(month_start)
        case "recently":
            return now.astimezone(UTC) - timedelta(days=RECENT_DAYS), now.astimezone(UTC) + timedelta(
                seconds=1
            )
    return None


def _date(value: str, ctx: LocaleContext) -> datetime:
    try:
        day = date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidFilter(f"invalid date {value!r}", extensions={"filter": "date"}) from exc
    return datetime.combine(day, time.min, tzinfo=_zone(ctx)).astimezone(UTC)


class QueryParser:
    def __init__(self, *, max_length: int = 256) -> None:
        self.max_length = max_length

    def parse(
        self,
        q: str,
        ctx: LocaleContext,
        *,
        now: datetime,
        mode: Mode = "mixed",
        filters: Mapping[str, Sequence[str] | str] | None = None,
        kinds: Sequence[str] | None = None,
    ) -> ParsedQuery:
        if len(q) > self.max_length:
            raise QueryTooLong(
                f"queries are limited to {self.max_length} characters",
                extensions={"max_length": self.max_length},
            )
        text = " ".join(q.replace("\x00", " ").split())
        collected: dict[str, list[str]] = {}
        for name, values in (filters or {}).items():
            items = [values] if isinstance(values, str) else list(values)
            collected.setdefault(name, []).extend(str(v) for v in items)

        def take(match: re.Match[str]) -> str:
            collected.setdefault(match.group(1), []).append(match.group(2).strip('"'))
            return " "

        text = " ".join(FILTER_TOKEN.sub(take, text).split())
        date_from: datetime | None = None
        date_to: datetime | None = None
        folded = normalize_for_search(text, ctx.language)
        for phrase in _PHRASES:
            pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)")
            hit = pattern.search(folded)
            if hit is None:
                continue
            collected.setdefault("date", []).append(RELATIVE[phrase])
            start, end = hit.span()  # NFC-folded text keeps the same length for these ASCII phrases
            if len(folded) == len(text):
                text = " ".join((text[:start] + " " + text[end:]).split())
            folded = normalize_for_search(text, ctx.language)
            break

        if len(collected) > MAX_FILTERS:
            raise InvalidFilter("too many filters")
        clean: dict[str, tuple[str, ...]] = {}
        kind_filter: list[str] = list(kinds or [])
        for name, values in collected.items():
            if not FILTER_NAME.fullmatch(name):
                raise InvalidFilter(f"invalid filter name {name[:32]!r}", extensions={"filter": name[:32]})
            values = [v.strip() for v in values if v and v.strip()]
            if len(values) > MAX_VALUES or any(len(v) > 64 for v in values):
                raise InvalidFilter(f"too many or too long values for {name!r}", extensions={"filter": name})
            if name in TYPE_FILTERS:
                kind_filter.extend(values)
            elif name == "date":
                for value in values:
                    span = relative_range(value, ctx, now)
                    if span is None:
                        raise InvalidFilter(f"unknown date range {value!r}", extensions={"filter": "date"})
                    date_from, date_to = span
            elif name == "after":
                date_from = _date(values[-1], ctx)
            elif name == "before":
                date_to = _date(values[-1], ctx)
            else:
                clean[name] = tuple(dict.fromkeys(values))
        normalized = normalize_for_search(text, ctx.language)
        terms = tuple(dict.fromkeys(t for t in re.split(r"[^\w]+", normalized) if t))
        return ParsedQuery(
            text=text,
            normalized=normalized,
            terms=terms,
            mode=mode,
            filters=clean,
            date_from=date_from,
            date_to=date_to,
            language=ctx.language,
            kinds=tuple(dict.fromkeys(kind_filter)) or None,
        )
