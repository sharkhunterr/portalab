"""014 T008 — occurrences: none / yearly / custom recurrences in the campaign time zone; DST gap and overlap
resolved by the 026 policy (gap → forward, overlap → earlier); leap-day and month-end anchors; start +
duration vs start/end; deterministic."""

from datetime import UTC, datetime
from typing import Any

from portalab.modules.campaigns.definitions.schema import parse_definition
from portalab.modules.campaigns.planner.planner import expand, resolve_wall_clock


def plan(schedule: dict[str, Any], tz: str = "Europe/Paris") -> list[tuple[datetime, datetime]]:
    definition = parse_definition({"names": {"en": "x"}, "timezone": tz, "schedule": schedule})
    return [(w.start_at, w.end_at) for w in expand(definition)]


def test_single_and_duration() -> None:
    assert plan({"start_at": "2026-10-20T00:00:00", "end_at": "2026-11-01T00:00:00"}) == [
        (datetime(2026, 10, 19, 22, tzinfo=UTC), datetime(2026, 10, 31, 23, tzinfo=UTC))  # DST ends Oct 25
    ]
    assert plan({"start_at": "2026-07-01T20:00:00", "duration_hours": 3}, "UTC") == [
        (datetime(2026, 7, 1, 20, tzinfo=UTC), datetime(2026, 7, 1, 23, tzinfo=UTC))
    ]


def test_yearly_and_leap_day() -> None:
    windows = plan(
        {
            "start_at": "2028-02-29T00:00:00",
            "duration_hours": 24,
            "recurrence": {"kind": "yearly", "count": 3},
        },
        "UTC",
    )
    assert [w[0].date().isoformat() for w in windows] == ["2028-02-29", "2029-02-28", "2030-02-28"]


def test_custom_weeks_and_month_end() -> None:
    weekly = plan(
        {
            "start_at": "2026-10-05T18:00:00",
            "duration_hours": 2,
            "recurrence": {"kind": "custom", "every": 2, "unit": "weeks", "count": 3},
        },
        "UTC",
    )
    assert [w[0].day for w in weekly] == [5, 19, 2]
    monthly = plan(
        {
            "start_at": "2026-01-31T10:00:00",
            "duration_hours": 1,
            "recurrence": {"kind": "custom", "every": 1, "unit": "months", "count": 4},
        },
        "UTC",
    )
    assert [w[0].date().isoformat() for w in monthly] == [
        "2026-01-31",
        "2026-02-28",
        "2026-03-31",
        "2026-04-30",
    ]


def test_dst_gap_and_overlap() -> None:
    gap = resolve_wall_clock(datetime(2026, 3, 29, 2, 30), "Europe/Paris")  # noqa: DTZ001 — wall clock  # 02:30 does not exist
    assert gap == datetime(2026, 3, 29, 1, 30, tzinfo=UTC)  # → 03:30 CEST
    overlap = resolve_wall_clock(datetime(2026, 10, 25, 2, 30), "Europe/Paris")  # noqa: DTZ001 — wall clock  # 02:30 exists twice
    assert overlap == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)  # the earlier one (CEST)
    nightly = plan(
        {
            "start_at": "2026-10-24T02:30:00",
            "duration_hours": 1,
            "recurrence": {"kind": "custom", "every": 1, "unit": "days", "count": 2},
        }
    )
    assert [w[0] for w in nightly] == [
        datetime(2026, 10, 24, 0, 30, tzinfo=UTC),
        datetime(2026, 10, 25, 0, 30, tzinfo=UTC),
    ]
    assert plan({"start_at": "2026-10-20T00:00:00", "end_at": "2026-11-01T00:00:00"}) == plan(
        {"start_at": "2026-10-20T00:00:00", "end_at": "2026-11-01T00:00:00"}
    )
