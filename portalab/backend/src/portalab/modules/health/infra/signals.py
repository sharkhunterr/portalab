"""Issue 122: what a server says, as service signals the automations watch — read from the report the
servers pages already keep a few seconds (no extra request to the server when they are open)."""

from collections.abc import Callable, Mapping
from typing import Any

from portalab.capabilities.health import INFRA_HOST
from portalab.capabilities.service_signals import Signal, SignalRegistry, Value
from portalab.modules.health.infra.hosts import HostService

OWNER = "module:health"


def _parity_running(report: Mapping[str, Any]) -> Value | None:
    parity = report.get("parity")
    if parity is None:
        return False if report.get("array_state") else None  # an array without a check under way
    return bool(parity.get("running")) or parity.get("status") in ("running", "paused")


def _parity_progress(report: Mapping[str, Any]) -> Value | None:
    parity = report.get("parity") or {}
    if not (parity.get("running") or parity.get("status") in ("running", "paused")):
        return None
    progress = parity.get("progress")
    return int(progress // 10 * 10) if isinstance(progress, int | float) else None  # by tens: 10, 20…


def _updates(report: Mapping[str, Any]) -> Value | None:
    containers = report.get("containers") or []
    return sum(1 for c in containers if c.get("update_available")) if containers else None


def _stopped(report: Mapping[str, Any]) -> Value | None:
    containers = report.get("containers") or []
    return sum(1 for c in containers if c.get("state") != "running") if containers else None


def _warnings(report: Mapping[str, Any]) -> Value | None:
    return ", ".join(sorted(report.get("warnings") or [])) or "none"


SIGNALS: tuple[tuple[str, str, Callable[[Mapping[str, Any]], Value | None], str, str], ...] = (
    ("infrastructure.parity_running", "bool", _parity_running, "Parity check running",
     "true while a parity check (or sync) runs or is paused on the server"),
    ("infrastructure.parity_progress", "number", _parity_progress, "Parity check progress",
     "how far the running parity check is, by tens of percent"),
    ("infrastructure.array_state", "text", lambda r: r.get("array_state"), "Array state",
     "the array's state (STARTED, STOPPED…)"),
    ("infrastructure.updates_available", "number", _updates, "Container updates available",
     "how many containers have an update waiting"),
    ("infrastructure.containers_stopped", "number", _stopped, "Containers not running",
     "how many containers are stopped or paused"),
    ("infrastructure.warnings", "text", _warnings, "Server warnings",
     "what the server says needs attention (storage_low, disk_errors…), « none » when all is well"),
)  # fmt: skip


def register_host_signals(hosts: HostService, registry: SignalRegistry) -> None:
    for key, kind, pick, label, description in SIGNALS:

        async def read(service_id: str, _provider: Any, pick: Any = pick) -> Value | None:
            entry = await hosts.report(service_id)
            report = (entry or {}).get("report") if (entry or {}).get("state") == "available" else None
            return pick(report) if report else None

        registry.register(
            Signal(key, OWNER, INFRA_HOST, kind, read, label=label, description=description)  # type: ignore[arg-type]
        )
