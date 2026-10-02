"""Connector ``ConformanceKit`` (T032; FR-033): every connector must pass it in CI.

Subclass it, return your connector and a :class:`ServiceHandle` per scenario (``ok``, ``slow`` beyond the
limit, ``garbage``, ``auth_error``, ``down``), and pytest runs the checks: health/test results are
actionable, timeouts are bounded, garbage payloads become typed results (never crashes), auth errors are
reported as such, sync output is well formed and idempotent (same source state ⇒ same records), and
nothing leaks the configured secrets.
"""

import asyncio
from typing import Any, ClassVar, Literal

from portalab.capabilities.connector_sdk import (
    Connector,
    ServiceHandle,
    SourceRecord,
    SyncProgress,
    TestResult,
)
from portalab.capabilities.isolation import IsolationPolicy, ProviderGuard
from portalab.capabilities.results import CapabilityResult, ProviderAuthError

Scenario = Literal["ok", "slow", "garbage", "auth_error", "down"]


class _Ctx:
    def __init__(self, service: ServiceHandle, capability: str) -> None:
        self.service = service
        self.capability = capability
        self.kind: Literal["manual"] = "manual"


class ConformanceKit:
    limit_seconds: ClassVar[float] = 0.5

    def make_connector(self) -> Connector:
        raise NotImplementedError

    def make_handle(self, scenario: Scenario) -> ServiceHandle:
        raise NotImplementedError

    async def _test(self, connector: Connector, handle: ServiceHandle) -> TestResult | None:
        try:
            return await asyncio.wait_for(connector.test_connection(handle), timeout=self.limit_seconds)
        except TimeoutError:
            return None
        except ProviderAuthError:
            return TestResult(ok=False, reachable=True, authenticated=False, detail="auth")

    async def _records(self, connector: Connector, handle: ServiceHandle) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        for binding in connector.provides:
            if not binding.syncable:
                continue
            async for item in connector.sync(_Ctx(handle, binding.spec.name), None):
                assert isinstance(item, SourceRecord | SyncProgress), "sync yields records or progress only"
                if isinstance(item, SourceRecord):
                    records.append(item)
        return records

    def _assert_no_secret(self, handle: ServiceHandle, *texts: str) -> None:
        for secret in handle.secrets.values():
            for text in texts:
                assert secret not in text, "a configured secret leaked into a result"

    async def test_manifest_and_bindings(self) -> None:
        connector = self.make_connector()
        assert connector.key and connector.manifest.version
        assert connector.provides, "a connector provides at least one capability"
        assert not set(connector.secret_fields) & set(connector.config_schema.model_fields)

    async def test_healthy_service_passes(self) -> None:
        connector, handle = self.make_connector(), self.make_handle("ok")
        result = await self._test(connector, handle)
        assert result is not None and result.ok and result.reachable and result.authenticated
        self._assert_no_secret(handle, result.detail)

    async def test_down_service_is_actionable(self) -> None:
        connector, handle = self.make_connector(), self.make_handle("down")
        result = await self._test(connector, handle)
        assert result is not None and not result.ok and not result.reachable and result.detail
        self._assert_no_secret(handle, result.detail)

    async def test_auth_error_is_reported(self) -> None:
        connector, handle = self.make_connector(), self.make_handle("auth_error")
        result = await self._test(connector, handle)
        assert result is not None and not result.ok and result.reachable and not result.authenticated

    async def test_slow_service_is_bounded(self) -> None:
        connector, handle = self.make_connector(), self.make_handle("slow")
        started = asyncio.get_running_loop().time()
        result = await self._test(connector, handle)
        assert result is None or not result.ok
        assert asyncio.get_running_loop().time() - started < self.limit_seconds * 4

    async def test_garbage_becomes_typed_result(self) -> None:
        connector, handle = self.make_connector(), self.make_handle("garbage")
        guard = ProviderGuard(
            source_system="conformance", policy=IsolationPolicy(timeout_seconds=1, max_retries=0)
        )
        for binding in connector.provides:
            provider = connector.provider(binding.spec.name, handle)
            for name in sorted(getattr(binding.spec.protocol, "__protocol_attrs__", ())):
                method: Any = getattr(provider, name)
                result: CapabilityResult[Any] = await guard.call(method)
                assert result.state in ("invalid_response", "unavailable"), result.state

    async def test_sync_is_idempotent(self) -> None:
        connector, handle = self.make_connector(), self.make_handle("ok")
        first = await self._records(connector, handle)
        second = await self._records(connector, handle)
        assert [(r.external_id, dict(r.payload)) for r in first] == [
            (r.external_id, dict(r.payload)) for r in second
        ]
        assert all(r.external_id and r.observed_at.tzinfo is not None for r in first)
