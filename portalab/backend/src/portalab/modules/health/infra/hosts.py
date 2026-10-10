"""Servers (#49 Glances, #50 Unraid): the full picture each ``infrastructure.host`` provider gives —
processor, memory, temperatures, disks, array, containers, updates — read through the service's provider
and kept a few seconds (several widgets and pages ask at once; Glances answers one request at a time).

``summary`` is what any member may see (how full the storage is, whether the server is fine); the full
report is for holders of ``infrastructure.read``."""

from dataclasses import asdict
from typing import Any

from portalab.capabilities.health import INFRA_HOST, HostReport, ReportCache
from portalab.capabilities.results import Available
from portalab.core.time import utc_now
from portalab.modules.health.state.service import StateService

CACHE_SECONDS = 20.0


class HostService:
    def __init__(self, state: StateService) -> None:
        self.state = state
        self._cache = ReportCache(fresh=CACHE_SECONDS, wait=8.0)

    def service_ids(self) -> list[str]:
        return [
            str(r.instance_ref)
            for r in self.state.capabilities.system_providers(INFRA_HOST)
            if r.instance_ref is not None
        ]

    def provider(self, service_id: str) -> Any:
        for registration in self.state.capabilities.system_providers(INFRA_HOST):
            if registration.instance_ref == service_id:
                return registration.provider
        return None

    async def report(self, service_id: str) -> dict[str, Any] | None:
        """The service's report as JSON-ready data; ``None`` when it has no host provider."""
        if self.provider(service_id) is None:
            return None
        found = await self._cache.get(service_id, lambda: self._load(service_id))
        if found is None:
            info = await self.state.service_info(service_id)
            return {
                "service_id": service_id,
                "name": info.name if info else service_id,
                "connector": info.connector if info else None,
                "as_of": utc_now(self.state.clock).isoformat(),
                "state": "unavailable",
                "report": None,
            }
        return found  # type: ignore[no-any-return]

    async def _load(self, service_id: str) -> dict[str, Any] | None:
        provider = self.provider(service_id)
        if provider is None:
            return None
        info = await self.state.service_info(service_id)
        base = {
            "service_id": service_id,
            "name": info.name if info else service_id,
            "connector": info.connector if info else None,
            "as_of": utc_now(self.state.clock).isoformat(),
        }
        result = await provider.report()
        if isinstance(result, Available) and isinstance(result.value, HostReport):
            return {**base, "state": "available", "report": serialize(result.value)}
        return None

    async def all(self) -> list[dict[str, Any]]:
        out = []
        for service_id in self.service_ids():
            report = await self.report(service_id)
            if report is not None:
                out.append(report)
        return out


def serialize(report: HostReport) -> dict[str, Any]:
    data = asdict(report)
    data["load"] = list(report.load) if report.load else None
    return data


def summary(entry: dict[str, Any]) -> dict[str, Any]:
    """What any member may see of a server: its name, whether it is fine, how full its storage is."""
    report = entry.get("report") or {}
    storage = report.get("storage") or {}
    return {
        "service_id": entry["service_id"],
        "name": entry["name"],
        "state": entry["state"],
        "storage": storage or None,
        "warnings": report.get("warnings") or [],
        "array_state": report.get("array_state"),
        "parity": report.get("parity"),
        "volumes": [
            {k: v.get(k) for k in ("name", "kind", "used", "total", "ok")}
            for v in report.get("volumes") or []
            if v.get("kind") != "share"
        ],
    }
