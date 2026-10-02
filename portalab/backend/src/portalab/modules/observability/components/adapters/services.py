"""Connector and sync adapters (T017/T018; FR-007, FR-010): one ``connector:<service>`` and one
``sync:<service>`` component per configured service, complementing (never replacing) Services & Health.

The connector complement tells apart: functional OK, external service unavailable, invalid credentials,
sync error and stale data. A service that answers probes but whose sync keeps failing is functionally
failing while its 006 state stays Operational."""

from collections.abc import Callable, Sequence
from datetime import timedelta
from typing import Any

from portalab.capabilities.health import SERVICE_DIRECTORY, SERVICE_STATE, ServiceInfo
from portalab.capabilities.observability import Check, CheckResult, DiagnosticAction, ObservedComponent
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.time import Clock, utc_now
from portalab.modules.observability.settings import ObservabilityConfig

OWNER = "module:observability"
_AUTH_HINTS = ("auth", "credential", "401", "403", "token")
_HEALTH = {"operational": "ok", "maintenance": "ok", "degraded": "degraded", "unavailable": "down"}


def _provider(capabilities: CapabilityRegistry, name: str) -> Any:
    providers = capabilities.system_providers(name)
    return providers[0].provider if providers else None


def sync_verdict(info: ServiceInfo, config: ObservabilityConfig, now: Any) -> CheckResult:
    error = (info.last_sync_error or "").lower()
    facts = {
        "sync_status": info.sync_status,
        "last_success_at": info.last_sync_success_at.isoformat() if info.last_sync_success_at else None,
    }
    if info.sync_status == "failed" and any(hint in error for hint in _AUTH_HINTS):
        return CheckResult("failing", "invalid_auth: the service rejects the configured credentials", facts)
    if info.sync_status == "failed":
        return CheckResult("failing", "sync_error: the last synchronization failed", facts)
    if info.last_sync_success_at is None:
        return CheckResult("unknown", "never synchronized", facts)
    if now - info.last_sync_success_at > timedelta(hours=config.sync_stale_hours):
        return CheckResult("degraded", "stale: no successful synchronization recently", facts)
    return CheckResult("ok", "synchronizations complete", facts)


def service_components(
    capabilities: CapabilityRegistry, config: Callable[[], ObservabilityConfig], clock: Clock | None
) -> Callable[[], Any]:
    async def source() -> Sequence[ObservedComponent]:
        directory = _provider(capabilities, SERVICE_DIRECTORY)
        if directory is None:
            return []
        components = []
        for info in await directory.services():
            if info.state in ("configured", "disconnected"):
                continue
            components.extend(_for_service(capabilities, info.id, info.name, config, clock))
        return components

    return source


def _for_service(
    capabilities: CapabilityRegistry,
    service_id: str,
    name: str,
    config: Callable[[], ObservabilityConfig],
    clock: Clock | None,
) -> list[ObservedComponent]:
    async def info() -> ServiceInfo | None:
        directory = _provider(capabilities, SERVICE_DIRECTORY)
        return await directory.service(service_id) if directory else None

    async def reachability() -> CheckResult:
        current = await info()
        if current is None:
            return CheckResult("unknown", "unknown service")
        if current.state == "disabled":
            return CheckResult("ok", "disabled by an administrator", {"connection": current.state})
        if current.state == "unavailable":
            return CheckResult(
                "down", "external_unavailable: the service does not answer", {"connection": current.state}
            )
        reader = _provider(capabilities, SERVICE_STATE)
        view = await reader.get(service_id) if reader else None
        if view is None:
            return CheckResult("unknown", "no health data yet", {"connection": current.state})
        state = _HEALTH.get(view.state, "unknown")
        reason = (
            "external_unavailable: the service does not answer"
            if state == "down"
            else f"service {view.state}"
        )
        return CheckResult(state, reason, {"health": view.state})  # type: ignore[arg-type]

    async def sync() -> CheckResult:
        current = await info()
        if current is None:
            return CheckResult("unknown", "unknown service")
        if current.state == "disabled":
            return CheckResult("ok", "disabled by an administrator")
        return sync_verdict(current, config(), utc_now(clock))

    diagnostics = (
        DiagnosticAction(
            "rerun_sync", "Synchronize now", "POST", f"/api/v1/services/{service_id}/sync", "services.manage"
        ),
        DiagnosticAction(
            "test_connector",
            "Test the connection",
            "POST",
            f"/api/v1/services/{service_id}/test",
            "services.manage",
        ),
        DiagnosticAction(
            "view_sync_history",
            "Sync history",
            "GET",
            f"/api/v1/services/{service_id}/sync-runs",
            "services.read",
        ),
    )
    return [
        ObservedComponent(
            f"connector:{service_id}",
            OWNER,
            kind="connector",
            label=name,
            technical_checks=(Check("reachability", reachability),),
            functional_checks=(Check("sync", sync),),
            diagnostics=diagnostics,
            impact=2,
            criticality=2,
        ),
        ObservedComponent(
            f"sync:{service_id}",
            OWNER,
            kind="sync",
            label=f"{name} sync",
            technical_checks=(Check("reachability", reachability),),
            functional_checks=(Check("sync", sync),),
            diagnostics=diagnostics[:1] + diagnostics[2:],
            impact=2,
            criticality=1,
        ),
    ]
