"""T025 — failure-isolating provider wrapper (contracts/capability-contract.md "Provision").

Exceptions, timeouts, garbage payloads and auth failures become typed results; retries are bounded with
jitter; last-known data is served as ``stale`` instead of failing.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from portalab.capabilities.isolation import IsolationPolicy, ProviderGuard
from portalab.capabilities.results import (
    AuthenticationFailed,
    Available,
    InvalidResponse,
    ProviderAuthError,
    Stale,
    Timeout,
    Unavailable,
)
from portalab.core.time import FixedClock

pytestmark = pytest.mark.contract

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


class Recorder:
    def __init__(self) -> None:
        self.sleeps: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def _guard(**policy: Any) -> tuple[ProviderGuard, Recorder, FixedClock]:
    recorder, clock = Recorder(), FixedClock(NOW)
    defaults: dict[str, Any] = {"timeout_seconds": 0.05, "max_retries": 2, "base_backoff_seconds": 0.1}
    defaults.update(policy)
    guard = ProviderGuard(
        source_system="fake",
        policy=IsolationPolicy(**defaults),
        clock=clock,
        sleep=recorder.sleep,
        jitter=lambda: 0.5,
    )
    return guard, recorder, clock


def _validate_int(payload: Any) -> int:
    if not isinstance(payload, int):
        raise ValueError("not an int")
    return payload


async def test_success_is_available_with_provenance_and_freshness() -> None:
    guard, _, _ = _guard()

    async def ok() -> int:
        return 42

    result = await guard.call(ok, validate=_validate_int, external_id="item-1")
    assert isinstance(result, Available)
    assert result.value == 42
    assert result.state == "available"
    assert result.as_of == NOW
    assert result.provenance is not None
    assert result.provenance.source_system == "fake"
    assert result.provenance.external_id == "item-1"


async def test_timeout_becomes_typed_result() -> None:
    guard, _, _ = _guard(max_retries=0)

    async def hang() -> int:
        await asyncio.sleep(5)
        return 1

    result = await guard.call(hang)
    assert isinstance(result, Timeout)
    assert result.state == "timeout"


async def test_garbage_payload_is_invalid_response_without_retry() -> None:
    guard, recorder, _ = _guard()
    calls = 0

    async def garbage() -> object:
        nonlocal calls
        calls += 1
        return {"unexpected": True}

    result = await guard.call(garbage, validate=_validate_int)
    assert isinstance(result, InvalidResponse)
    assert calls == 1
    assert recorder.sleeps == []


async def test_auth_failure_is_typed_and_not_retried() -> None:
    guard, _, _ = _guard()
    calls = 0

    async def denied() -> int:
        nonlocal calls
        calls += 1
        raise ProviderAuthError("token=abcdef123456 rejected")

    result = await guard.call(denied)
    assert isinstance(result, AuthenticationFailed)
    assert calls == 1
    assert "abcdef123456" not in (result.detail or "")


async def test_unexpected_exception_is_retried_with_bounded_jittered_backoff() -> None:
    guard, recorder, _ = _guard(max_retries=2, base_backoff_seconds=0.1)
    calls = 0

    async def flaky() -> int:
        nonlocal calls
        calls += 1
        raise ConnectionError("boom")

    result = await guard.call(flaky)
    assert isinstance(result, Unavailable)
    assert calls == 3  # first attempt + 2 retries
    # exponential backoff: base * 2**attempt, scaled by jitter factor in [0.5, 1.5)
    assert recorder.sleeps == pytest.approx([0.1 * 1.0, 0.2 * 1.0])


async def test_retry_then_success() -> None:
    guard, _, _ = _guard(max_retries=2)
    calls = 0

    async def second_time_lucky() -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("transient")
        return 7

    result = await guard.call(second_time_lucky, validate=_validate_int)
    assert isinstance(result, Available)
    assert result.value == 7


async def test_last_known_data_is_served_as_stale() -> None:
    guard, _, clock = _guard(max_retries=0)

    async def ok() -> int:
        return 5

    async def down() -> int:
        raise ConnectionError("outage")

    first = await guard.call(ok, validate=_validate_int, cache_key="k")
    assert isinstance(first, Available)
    clock.advance(timedelta(minutes=10))
    second = await guard.call(down, validate=_validate_int, cache_key="k")
    assert isinstance(second, Stale)
    assert second.value == 5
    assert second.as_of == NOW
    assert second.reason == "unavailable"
    other_key = await guard.call(down, cache_key="other")
    assert isinstance(other_key, Unavailable)


async def test_guard_never_raises_even_on_base_exceptions_from_validation() -> None:
    guard, _, _ = _guard(max_retries=0)

    async def ok() -> int:
        return 1

    def explode(_: Any) -> int:
        raise KeyError("weird")

    result = await guard.call(ok, validate=explode)
    assert isinstance(result, InvalidResponse)


async def test_health_is_separate_and_isolated() -> None:
    guard, _, _ = _guard(max_retries=0)

    class Provider:
        async def health(self) -> bool:
            raise ConnectionError("unreachable")

    health = await guard.health(Provider())
    assert health.state == "unavailable"

    class Healthy:
        async def health(self) -> bool:
            return True

    assert (await guard.health(Healthy())).state == "available"
    assert (await guard.health(object())).state == "unknown"
