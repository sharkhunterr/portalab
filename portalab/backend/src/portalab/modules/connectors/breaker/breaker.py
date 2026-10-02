"""Per-service circuit breaker (T027; R5, FR-010..013).

``closed`` → (``threshold`` consecutive failures) → ``open`` → (after ``open_seconds``) → ``half_open``:
one probe is let through; success closes the circuit, failure re-opens it. Breakers are per service, so
an outage of one service never affects another. Transitions are reported to a callback so the manager can
move the persisted service state to ``unavailable`` and back.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from portalab.core.time import Clock, utc_now

BreakerState = Literal["closed", "open", "half_open"]
Listener = Callable[[BreakerState, BreakerState], Awaitable[None]]


@dataclass
class CircuitBreaker:
    threshold: int = 5
    open_seconds: float = 60.0
    clock: Clock | None = None
    state: BreakerState = "closed"
    failures: int = 0
    opened_at: datetime | None = None
    listener: Listener | None = None

    def _now(self) -> datetime:
        return utc_now(self.clock)

    def current(self) -> BreakerState:
        if (
            self.state == "open"
            and self.opened_at is not None
            and self._now() - self.opened_at >= timedelta(seconds=self.open_seconds)
        ):
            self.state = "half_open"
        return self.state

    def allow(self) -> bool:
        """True when a call may go through (closed, or the half-open probe)."""
        return self.current() != "open"

    async def _move(self, to: BreakerState) -> None:
        before, self.state = self.state, to
        if before != to and self.listener is not None:
            await self.listener(before, to)

    async def record_success(self) -> None:
        state = self.current()
        self.failures = 0
        self.opened_at = None
        if state != "closed":
            await self._move("closed")

    async def record_failure(self) -> None:
        self.failures += 1
        state = self.current()
        if state == "half_open" or (state == "closed" and self.failures >= self.threshold):
            self.opened_at = self._now()
            await self._move("open")


class BreakerBoard:
    """One breaker per service (in-process; the persisted service state is shared across processes)."""

    def __init__(self, *, threshold: int = 5, open_seconds: float = 60.0, clock: Clock | None = None) -> None:
        self.threshold = threshold
        self.open_seconds = open_seconds
        self.clock = clock
        self._breakers: dict[str, CircuitBreaker] = {}
        self.listener_factory: Callable[[str], Listener] | None = None

    def get(self, service_id: str) -> CircuitBreaker:
        breaker = self._breakers.get(service_id)
        if breaker is None:
            listener = self.listener_factory(service_id) if self.listener_factory else None
            breaker = CircuitBreaker(self.threshold, self.open_seconds, self.clock, listener=listener)
            self._breakers[service_id] = breaker
        return breaker

    def configure(self, *, threshold: int, open_seconds: float) -> None:
        self.threshold, self.open_seconds = threshold, open_seconds
        for breaker in self._breakers.values():
            breaker.threshold, breaker.open_seconds = threshold, open_seconds

    def forget(self, service_id: str) -> None:
        self._breakers.pop(service_id, None)

    def snapshot(self) -> dict[str, BreakerState]:
        return {key: breaker.current() for key, breaker in self._breakers.items()}
