"""005 T026 — circuit breaker: opens after repeated failures, half-open probe recovers or re-opens."""

from datetime import UTC, datetime, timedelta

from portalab.core.time import FixedClock
from portalab.modules.connectors.breaker.breaker import BreakerBoard, CircuitBreaker


async def test_open_half_open_close() -> None:
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    moves: list[tuple[str, str]] = []

    async def listener(before: str, after: str) -> None:
        moves.append((before, after))

    breaker = CircuitBreaker(threshold=2, open_seconds=30, clock=clock, listener=listener)  # type: ignore[arg-type]
    await breaker.record_failure()
    assert breaker.allow()
    await breaker.record_failure()
    assert not breaker.allow() and breaker.current() == "open"
    clock.advance(timedelta(seconds=31))
    assert breaker.allow() and breaker.current() == "half_open"
    await breaker.record_failure()  # failed probe re-opens
    assert breaker.current() == "open"
    clock.advance(timedelta(seconds=31))
    await breaker.record_success()
    assert breaker.current() == "closed" and breaker.failures == 0
    assert moves == [("closed", "open"), ("half_open", "open"), ("half_open", "closed")]


async def test_breakers_are_per_service() -> None:
    board = BreakerBoard(threshold=1)
    await board.get("a").record_failure()
    assert board.get("a").current() == "open" and board.get("b").current() == "closed"
