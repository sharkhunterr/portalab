"""T007 — UUIDv7 ids, injectable clock, occurred_at/received_at helpers (research R7, CD-012)."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from portalab.core.ids import new_id
from portalab.core.time import FixedClock, Occurrence, SystemClock, require_aware, utc_now

pytestmark = pytest.mark.unit


def test_new_id_is_uuid_version_7() -> None:
    value = new_id()
    assert isinstance(value, UUID)
    assert type(value) is UUID  # plain stdlib UUID, no library subclass leaks out
    assert value.version == 7


def test_new_ids_are_unique_and_time_ordered() -> None:
    ids = [new_id() for _ in range(2000)]
    assert len(set(ids)) == len(ids)
    assert ids == sorted(ids)


def test_system_clock_returns_aware_utc() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_clock_is_injectable() -> None:
    instant = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    clock = FixedClock(instant)
    assert utc_now(clock) == instant
    clock.advance(timedelta(minutes=5))
    assert utc_now(clock) == instant + timedelta(minutes=5)


def test_fixed_clock_rejects_naive_instant() -> None:
    with pytest.raises(ValueError):
        FixedClock(datetime(2026, 10, 1, 12, 0))  # noqa: DTZ001


def test_require_aware_rejects_naive_and_normalizes_to_utc() -> None:
    with pytest.raises(ValueError):
        require_aware(datetime(2026, 10, 1, 12, 0))  # noqa: DTZ001
    paris_summer = timezone(timedelta(hours=2))
    normalized = require_aware(datetime(2026, 7, 1, 14, 0, tzinfo=paris_summer))
    assert normalized == datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    assert normalized.utcoffset() == timedelta(0)


def test_occurrence_requires_aware_instants() -> None:
    aware = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError):
        Occurrence(occurred_at=datetime(2026, 10, 1, 12, 0), received_at=aware)  # noqa: DTZ001
    with pytest.raises(ValueError):
        Occurrence(occurred_at=aware, received_at=datetime(2026, 10, 1, 12, 0))  # noqa: DTZ001


def test_occurrence_received_at_comes_from_clock() -> None:
    received = datetime(2026, 10, 1, 13, 0, tzinfo=UTC)
    occurred = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    occurrence = Occurrence.observed(occurred, clock=FixedClock(received))
    assert occurrence.occurred_at == occurred
    assert occurrence.received_at == received


def test_received_at_is_never_part_of_identity() -> None:
    occurred = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    first = Occurrence(occurred_at=occurred, received_at=occurred + timedelta(seconds=1))
    late = Occurrence(occurred_at=occurred, received_at=occurred + timedelta(hours=3))
    assert first.identity_instant == late.identity_instant == occurred
    assert first.same_occurrence_time(late)
