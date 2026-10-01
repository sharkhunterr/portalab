"""Typed capability results (contracts/capability-contract.md).

A provider call never surfaces as an unhandled exception: it yields one of these states so consumers can
render ``available / partial / stale / unavailable / no data`` (functional states, CD-022) instead of failing.
Data-carrying results hold ``provenance`` (source of truth, CD-014/026) and freshness ``as_of``.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

ResultState = Literal[
    "available",
    "partial",
    "stale",
    "unavailable",
    "timeout",
    "invalid_response",
    "authentication_failed",
    "no_provider",
]


class ProviderAuthError(Exception):
    """Raised by connectors when the external service rejects the configured credentials."""


class InvalidPayload(Exception):
    """Raised by connectors (or validators) when an external payload does not match the contract."""


@dataclass(frozen=True, slots=True)
class Provenance:
    source_system: str
    external_id: str | None
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class CapabilityResult[T]:
    """Base of every result; ``has_data`` tells whether ``value`` may be rendered."""

    @property
    def state(self) -> ResultState:
        raise NotImplementedError

    @property
    def has_data(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Available[T](CapabilityResult[T]):
    value: T
    as_of: datetime
    provenance: Provenance | None = None

    @property
    def state(self) -> ResultState:
        return "available"

    @property
    def has_data(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class Partial[T](CapabilityResult[T]):
    value: T
    as_of: datetime
    missing: tuple[str, ...] = ()
    provenance: Provenance | None = None

    @property
    def state(self) -> ResultState:
        return "partial"

    @property
    def has_data(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class Stale[T](CapabilityResult[T]):
    """Last-known data served while the source is failing; ``reason`` is the failure state."""

    value: T
    as_of: datetime
    reason: ResultState
    provenance: Provenance | None = None

    @property
    def state(self) -> ResultState:
        return "stale"

    @property
    def has_data(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class _Failure[T](CapabilityResult[T]):
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class Unavailable[T](_Failure[T]):
    @property
    def state(self) -> ResultState:
        return "unavailable"


@dataclass(frozen=True, slots=True)
class Timeout[T](_Failure[T]):
    @property
    def state(self) -> ResultState:
        return "timeout"


@dataclass(frozen=True, slots=True)
class InvalidResponse[T](_Failure[T]):
    @property
    def state(self) -> ResultState:
        return "invalid_response"


@dataclass(frozen=True, slots=True)
class AuthenticationFailed[T](_Failure[T]):
    @property
    def state(self) -> ResultState:
        return "authentication_failed"


@dataclass(frozen=True, slots=True)
class NoProvider[T](_Failure[T]):
    capability: str = ""

    @property
    def state(self) -> ResultState:
        return "no_provider"


@dataclass(frozen=True, slots=True)
class HealthResult:
    """Technical health of a provider — separate from its sync state (owned by spec 005)."""

    state: Literal["available", "unavailable", "unknown"]
    checked_at: datetime
    detail: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
