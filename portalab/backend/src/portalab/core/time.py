"""Time helpers: injectable clock, aware-UTC enforcement, occurrence instants (CD-012).

* every instant is timezone-aware and normalized to UTC;
* occurrence facts carry ``occurred_at`` (real occurrence) and ``received_at`` (portal receipt);
* ``received_at`` is never used as an identity or deduplication key.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """Source of the current instant; injected wherever time matters so tests stay deterministic."""

    def now(self) -> datetime: ...


class SystemClock:
    """Wall clock in UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Deterministic clock for tests and replays."""

    def __init__(self, instant: datetime) -> None:
        self._instant = require_aware(instant)

    def now(self) -> datetime:
        return self._instant

    def set(self, instant: datetime) -> None:
        self._instant = require_aware(instant)

    def advance(self, delta: timedelta) -> None:
        self._instant = self._instant + delta


_DEFAULT_CLOCK: Clock = SystemClock()


def utc_now(clock: Clock | None = None) -> datetime:
    """Current UTC instant from ``clock`` (system clock by default)."""
    return require_aware((clock or _DEFAULT_CLOCK).now())


def require_aware(value: datetime) -> datetime:
    """Reject naive datetimes and normalize aware ones to UTC."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("naive datetime rejected: instants must be timezone-aware (stored as UTC)")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class Occurrence:
    """When something really happened versus when the portal learned about it."""

    occurred_at: datetime
    received_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_at", require_aware(self.occurred_at))
        object.__setattr__(self, "received_at", require_aware(self.received_at))

    @classmethod
    def observed(cls, occurred_at: datetime, *, clock: Clock | None = None) -> "Occurrence":
        """Build an occurrence received now (per ``clock``)."""
        return cls(occurred_at=occurred_at, received_at=utc_now(clock))

    @property
    def identity_instant(self) -> datetime:
        """The only instant that may take part in an identity/dedup key: the real occurrence time."""
        return self.occurred_at

    def same_occurrence_time(self, other: "Occurrence") -> bool:
        return self.occurred_at == other.occurred_at
