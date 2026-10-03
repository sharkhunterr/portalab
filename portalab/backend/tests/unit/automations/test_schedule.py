"""019 T020 — time triggers: ``at``; ``recurring`` daily / weekly / monthly at HH:MM in a time zone with DST
(a missing wall time moves forward, a repeated one takes the earlier instant); no cron strings;
deterministic next-fire computation."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from portalab.modules.automations.definitions.schema import Trigger
from portalab.modules.automations.scheduler.scheduler import next_fire


def recurring(**schedule: object) -> Trigger:
    return Trigger.model_validate({"kind": "recurring", "schedule": schedule, "timezone": "Europe/Paris"})


def test_at_and_recurring() -> None:
    at = Trigger.model_validate({"kind": "at", "at": "2026-10-10T08:00:00+00:00"})
    assert next_fire(at, datetime(2026, 10, 1, tzinfo=UTC)) == datetime(2026, 10, 10, 8, tzinfo=UTC)
    assert next_fire(at, datetime(2026, 10, 11, tzinfo=UTC)) is None
    daily = recurring(frequency="daily", time="09:00")
    assert next_fire(daily, datetime(2026, 10, 1, 6, tzinfo=UTC)) == datetime(2026, 10, 1, 7, tzinfo=UTC)
    assert next_fire(daily, datetime(2026, 10, 1, 7, tzinfo=UTC)) == datetime(2026, 10, 2, 7, tzinfo=UTC)
    weekly = recurring(frequency="weekly", weekday=0, time="09:00")
    assert next_fire(weekly, datetime(2026, 10, 1, tzinfo=UTC)) == datetime(2026, 10, 5, 7, tzinfo=UTC)
    monthly = recurring(frequency="monthly", day=15, time="20:00")
    assert next_fire(monthly, datetime(2026, 10, 20, tzinfo=UTC)) == datetime(2026, 11, 15, 19, tzinfo=UTC)
    assert next_fire(daily, datetime(2026, 10, 1, 6, tzinfo=UTC)) == next_fire(
        daily, datetime(2026, 10, 1, 6, tzinfo=UTC)
    )


def test_dst() -> None:
    gap = recurring(frequency="daily", time="02:30")  # Mar 29 2026: 02:30 does not exist in Paris
    assert next_fire(gap, datetime(2026, 3, 28, 23, tzinfo=UTC)) == datetime(2026, 3, 29, 1, 30, tzinfo=UTC)
    overlap = recurring(frequency="daily", time="02:30")  # Oct 25 2026: 02:30 happens twice
    assert next_fire(overlap, datetime(2026, 10, 24, 23, tzinfo=UTC)) == datetime(
        2026, 10, 25, 0, 30, tzinfo=UTC
    )


@pytest.mark.parametrize(
    "raw",
    [
        {"kind": "recurring", "schedule": {"cron": "0 9 * * 1"}},
        {"kind": "recurring", "schedule": {"frequency": "hourly", "time": "09:00"}},
        {"kind": "recurring", "schedule": {"frequency": "weekly", "time": "09:00"}},
        {"kind": "recurring", "schedule": {"frequency": "daily", "time": "25:00"}},
        {"kind": "at", "at": "2026-10-10T08:00:00"},
    ],
)
def test_rejections(raw: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Trigger.model_validate(raw)
