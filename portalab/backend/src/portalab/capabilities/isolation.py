"""Failure-isolating provider wrapper (plan §7, principle IX).

Every call to an external provider goes through :class:`ProviderGuard`:
* per-call timeout;
* bounded retries with exponential backoff and jitter for transient failures only;
* exceptions → typed results (never an unhandled crash); auth and payload errors are not retried;
* last-known good data is served as :class:`Stale` while the source fails (no deletion, CD-014);
* ``health()`` is evaluated separately from data calls and from sync state (owned by spec 005).
"""

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from portalab.capabilities.results import (
    AuthenticationFailed,
    Available,
    CapabilityResult,
    HealthResult,
    InvalidPayload,
    InvalidResponse,
    Provenance,
    ProviderAuthError,
    Stale,
    Timeout,
    Unavailable,
)
from portalab.core.logging import get_logger, redact_text
from portalab.core.time import Clock, SystemClock

log = get_logger("portalab.capabilities.isolation")

Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class IsolationPolicy:
    timeout_seconds: float = 10.0
    max_retries: int = 2
    base_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 10.0


def _default_jitter() -> float:
    return random.random()  # noqa: S311 — jitter, not cryptography


class ProviderGuard:
    def __init__(
        self,
        *,
        source_system: str,
        policy: IsolationPolicy | None = None,
        clock: Clock | None = None,
        sleep: Sleep = asyncio.sleep,
        jitter: Callable[[], float] = _default_jitter,
    ) -> None:
        self.source_system = source_system
        self.policy = policy or IsolationPolicy()
        self._clock = clock or SystemClock()
        self._sleep = sleep
        self._jitter = jitter
        self._last_known: dict[str, tuple[Any, datetime, Provenance | None]] = {}

    def _backoff(self, attempt: int) -> float:
        delay = min(self.policy.base_backoff_seconds * float(2**attempt), self.policy.max_backoff_seconds)
        return delay * (0.5 + self._jitter())

    def _fallback[T](self, cache_key: str | None, failure: CapabilityResult[T]) -> CapabilityResult[T]:
        if cache_key is not None and cache_key in self._last_known:
            value, as_of, provenance = self._last_known[cache_key]
            return Stale(value=value, as_of=as_of, reason=failure.state, provenance=provenance)
        return failure

    def fallback[T](self, cache_key: str | None, failure: CapabilityResult[T]) -> CapabilityResult[T]:
        """Last-known data as :class:`Stale` (or ``failure`` when nothing is cached), without calling."""
        return self._fallback(cache_key, failure)

    async def call[T](
        self,
        operation: Callable[[], Awaitable[Any]],
        *,
        validate: Callable[[Any], T] | None = None,
        cache_key: str | None = None,
        external_id: str | None = None,
    ) -> CapabilityResult[T]:
        failure: CapabilityResult[T] = Unavailable(detail="provider unavailable")
        for attempt in range(self.policy.max_retries + 1):
            try:
                payload = await asyncio.wait_for(operation(), timeout=self.policy.timeout_seconds)
            except TimeoutError:
                failure = Timeout(detail="provider did not answer in time")
            except ProviderAuthError as exc:
                return AuthenticationFailed(detail=redact_text(str(exc)) or None)
            except InvalidPayload as exc:
                return self._fallback(cache_key, InvalidResponse(detail=redact_text(str(exc))))
            except Exception as exc:
                log.warning(
                    "provider call failed",
                    extra={"fields": {"source_system": self.source_system, "error": type(exc).__name__}},
                )
                failure = Unavailable(detail="provider call failed")
            else:
                try:
                    value: T = validate(payload) if validate else payload
                except Exception as exc:
                    return self._fallback(cache_key, InvalidResponse(detail=redact_text(str(exc))))
                now = self._clock.now()
                provenance = Provenance(self.source_system, external_id, now)
                if cache_key is not None:
                    self._last_known[cache_key] = (value, now, provenance)
                return Available(value=value, as_of=now, provenance=provenance)
            if attempt < self.policy.max_retries:
                await self._sleep(self._backoff(attempt))
        return self._fallback(cache_key, failure)

    async def health(self, provider: object) -> HealthResult:
        checked_at = self._clock.now()
        probe = getattr(provider, "health", None)
        if probe is None or not callable(probe):
            return HealthResult(state="unknown", checked_at=checked_at)
        try:
            healthy = await asyncio.wait_for(probe(), timeout=self.policy.timeout_seconds)
        except Exception:
            return HealthResult(state="unavailable", checked_at=checked_at, detail="health check failed")
        return HealthResult(state="available" if healthy else "unavailable", checked_at=checked_at)
