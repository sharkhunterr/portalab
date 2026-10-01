"""Capability conformance kit + fake external service (contracts/capability-contract.md "Conformance").

Every connector/provider of a capability must pass the kit in CI. Usage in a test module::

    class TestMyConnector(CapabilityConformanceKit):
        capability = "media.library"

        def make_provider(self, service: FakeExternalService) -> Any:
            return MyConnector(client=service)

        async def invoke(self, guard: ProviderGuard, provider: Any) -> CapabilityResult[Any]:
            return await guard.call(provider.list_items, validate=parse_items)

The fake service simulates the failure modes a real one exhibits: latency, hangs, garbage payloads,
authentication errors and transient failures.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

from portalab.capabilities.isolation import IsolationPolicy, ProviderGuard
from portalab.capabilities.results import (
    AuthenticationFailed,
    Available,
    CapabilityResult,
    InvalidResponse,
    ProviderAuthError,
    Stale,
    Timeout,
    Unavailable,
)
from portalab.core.time import FixedClock

Mode = Literal["ok", "slow", "hang", "garbage", "auth_error", "error", "flaky"]

GARBAGE: Any = {"\u0000unexpected": ["not", "the", "contract"], "id": None}


@dataclass
class FakeExternalService:
    """Programmable stand-in for an external service API."""

    payload: Any = None
    mode: Mode = "ok"
    latency_seconds: float = 0.0
    failures_before_success: int = 0
    calls: int = field(default=0, init=False)

    async def fetch(self, *_: Any, **__: Any) -> Any:
        self.calls += 1
        if self.latency_seconds:
            await asyncio.sleep(self.latency_seconds)
        if self.mode == "hang":
            await asyncio.sleep(3600)
        if self.mode == "garbage":
            return GARBAGE
        if self.mode == "auth_error":
            raise ProviderAuthError("credentials rejected by the external service")
        if self.mode == "error":
            raise ConnectionError("external service unavailable")
        if self.mode == "flaky" and self.calls <= self.failures_before_success:
            raise ConnectionError("transient failure")
        return self.payload


class CapabilityConformanceKit:
    """Base class: subclasses provide the provider factory and how to invoke the capability."""

    capability: ClassVar[str] = ""
    valid_payload: ClassVar[Any] = None
    policy: ClassVar[IsolationPolicy] = IsolationPolicy(
        timeout_seconds=0.2, max_retries=1, base_backoff_seconds=0.0
    )

    def make_provider(self, service: FakeExternalService) -> Any:
        raise NotImplementedError

    async def invoke(self, guard: ProviderGuard, provider: Any) -> CapabilityResult[Any]:
        raise NotImplementedError

    # ----------------------------------------------------------------------------------------------
    def _guard(self) -> ProviderGuard:
        async def no_sleep(_: float) -> None:
            return None

        return ProviderGuard(
            source_system=f"conformance:{self.capability}",
            policy=self.policy,
            clock=FixedClock(datetime(2026, 1, 1, tzinfo=UTC)),
            sleep=no_sleep,
            jitter=lambda: 0.5,
        )

    async def _run(self, **service_options: Any) -> CapabilityResult[Any]:
        service = FakeExternalService(payload=self.valid_payload, **service_options)
        return await self.invoke(self._guard(), self.make_provider(service))

    async def test_conformance_available_on_healthy_service(self) -> None:
        result = await self._run()
        assert isinstance(result, Available), result
        assert result.provenance is not None

    async def test_conformance_timeout_is_typed(self) -> None:
        assert isinstance(await self._run(mode="hang"), Timeout)

    async def test_conformance_garbage_is_invalid_response(self) -> None:
        assert isinstance(await self._run(mode="garbage"), InvalidResponse)

    async def test_conformance_auth_error_is_typed(self) -> None:
        assert isinstance(await self._run(mode="auth_error"), AuthenticationFailed)

    async def test_conformance_outage_is_unavailable_not_exception(self) -> None:
        assert isinstance(await self._run(mode="error"), Unavailable | Stale)

    async def test_conformance_transient_failure_is_retried(self) -> None:
        result = await self._run(mode="flaky", failures_before_success=1)
        assert isinstance(result, Available), result
