"""Server widgets (#49 Glances, #50 Unraid), from the services' ``infrastructure.host`` providers:

* ``health.host`` — the server at a glance: processor, memory, hottest sensor, network, uptime, what needs
  attention (``infrastructure.read``);
* ``health.storage`` — how full the storage is: the whole, each disk and cache, the array and its parity
  check (any member: ``services.read`` — no names of containers or files);
* ``health.containers`` — the containers: how many run, which have an update, the server's unread
  notifications (``infrastructure.read``).

The server is the one chosen in the widget's settings, else the first that reports one (for the storage,
the first with an array). Reports are kept a few seconds: several widgets ask at once."""

import time
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from portalab.capabilities.dashboard import (
    Refresh,
    Size,
    SizeLimits,
    WidgetDefinition,
    WidgetPayload,
    WidgetUnavailable,
)
from portalab.capabilities.health import INFRA_HOST, SERVICE_DIRECTORY, HostReport
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.results import Available
from portalab.core.authz_port import Principal
from portalab.core.time import Clock, utc_now

OWNER = "module:dashboard"
SERVICES_READ = "services.read"
INFRASTRUCTURE_READ = "infrastructure.read"
CACHE_SECONDS = 20.0
SERVICE_SETTING = {"service": {"type": "string", "maxLength": 64, "x-options": "services"}}


def _definition(
    key: str, icon: str, permission: str, default: Size, extra: Mapping[str, Any]
) -> WidgetDefinition:
    name = key.split(".")[1]
    return WidgetDefinition(
        key=key,
        owner=OWNER,
        title_key=f"dashboard:widget.{name}.title",
        description_key=f"dashboard:widget.{name}.description",
        icon=icon,
        required_permission=permission,
        config_schema={
            "type": "object",
            "properties": {**SERVICE_SETTING, **extra},
            "additionalProperties": False,
        },
        config_defaults={"service": ""},
        size=SizeLimits(default=default, min=Size(3, 1), max=Size(12, 6)),
        refresh=Refresh(mode="interval", interval_s=60),
        stale_after_s=300,
        component_id=key,
        multiple=True,
    )


HOST = _definition("health.host", "cpu", INFRASTRUCTURE_READ, Size(6, 2), {})
STORAGE = _definition("health.storage", "database", SERVICES_READ, Size(6, 3), {})
CONTAINERS = _definition(
    "health.containers",
    "package",
    INFRASTRUCTURE_READ,
    Size(6, 3),
    {"show": {"enum": ["updates", "all", "stopped"]}},
)


class HostReports:
    """The reports of the servers, kept ``CACHE_SECONDS`` (shared by the three widgets)."""

    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities
        self._cache: dict[str, tuple[float, HostReport | None]] = {}

    def services(self) -> list[str]:
        try:
            registrations = self.capabilities.system_providers(INFRA_HOST)
        except Exception:
            return []
        return [str(r.instance_ref) for r in registrations if r.instance_ref is not None]

    async def get(self, service_id: str) -> HostReport | None:
        cached = self._cache.get(service_id)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        report: HostReport | None = None
        for registration in self.capabilities.system_providers(INFRA_HOST):
            if registration.instance_ref == service_id:
                result = await registration.provider.report()
                if isinstance(result, Available) and isinstance(result.value, HostReport):
                    report = result.value
        self._cache[service_id] = (time.monotonic(), report)
        return report

    async def name(self, service_id: str) -> str:
        try:
            providers = self.capabilities.system_providers(SERVICE_DIRECTORY)
            info = await providers[0].provider.service(service_id) if providers else None
        except Exception:
            info = None
        return info.name if info is not None else service_id

    async def pick(self, config: Mapping[str, Any], *, array: bool = False) -> tuple[str, HostReport]:
        chosen = str(config.get("service") or "")
        candidates = [chosen] if chosen else self.services()
        if not candidates:
            raise WidgetUnavailable("no server is watched")
        reports = [(sid, await self.get(sid)) for sid in candidates]
        found = [(sid, r) for sid, r in reports if r is not None]
        if not found:
            raise WidgetUnavailable("the server does not answer")
        if array:
            found.sort(key=lambda item: item[1].array_state is None)
        return found[0]


class _Base:
    def __init__(self, reports: HostReports, clock: Clock | None = None) -> None:
        self.reports = reports
        self.clock = clock


class HostProvider(_Base):
    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        service_id, report = await self.reports.pick(config)
        temps = [s for s in report.sensors if s.unit == "°C"]
        hottest = max(temps, key=lambda s: s.value) if temps else None
        rx = sum(i.rx_bps or 0 for i in report.interfaces) if report.interfaces else None
        tx = sum(i.tx_bps or 0 for i in report.interfaces) if report.interfaces else None
        running = sum(1 for c in report.containers if c.state == "running")
        data = {
            "service_id": service_id,
            "name": await self.reports.name(service_id),
            "hostname": report.hostname,
            "os": report.os,
            "cpu_name": report.cpu_name,
            "cpu_cores": report.cpu_cores,
            "uptime_seconds": report.uptime_seconds,
            "cpu": report.cpu_percent,
            "load": list(report.load) if report.load else None,
            "memory": asdict(report.memory) if report.memory else None,
            "storage": asdict(report.storage) if report.storage else None,
            "temperature": {"label": hottest.label, "value": hottest.value} if hottest else None,
            "network": {"rx": rx, "tx": tx} if rx is not None else None,
            "containers": {"running": running, "total": len(report.containers)}
            if report.containers
            else None,
            "updates": sum(1 for c in report.containers if c.update_available),
            "warnings": list(report.warnings),
        }
        return WidgetPayload("available", as_of=utc_now(self.clock), data=data)


class StorageProvider(_Base):
    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        service_id, report = await self.reports.pick(config, array=True)
        volumes = [
            {
                "name": v.name,
                "kind": v.kind,
                "used": v.used,
                "total": v.total,
                "ok": v.ok,
                "temperature": v.temperature,
                "spinning": v.spinning,
            }
            for v in report.volumes
            if v.kind not in ("share", "boot") and v.total
        ]
        if not volumes and report.storage is None:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        data = {
            "service_id": service_id,
            "name": await self.reports.name(service_id),
            "storage": asdict(report.storage) if report.storage else None,
            "array_state": report.array_state,
            "parity": asdict(report.parity) if report.parity else None,
            "volumes": volumes,
            "warnings": [
                w
                for w in report.warnings
                if w in ("storage_low", "disk_problem", "disk_errors", "array_stopped")
            ],
        }
        return WidgetPayload("available", as_of=utc_now(self.clock), data=data)


class ContainersProvider(_Base):
    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        service_id, report = await self.reports.pick(config)
        if not report.containers and not report.notices:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        show = str(config.get("show") or "updates")
        containers = list(report.containers)
        listed = {
            "updates": [c for c in containers if c.update_available],
            "stopped": [c for c in containers if c.state != "running"],
            "all": containers,
        }.get(show, containers)
        data = {
            "service_id": service_id,
            "name": await self.reports.name(service_id),
            "running": sum(1 for c in containers if c.state == "running"),
            "total": len(containers),
            "updates": sum(1 for c in containers if c.update_available),
            "updates_known": any(c.update_available is not None for c in containers),
            "items": [
                {
                    "name": c.name,
                    "state": c.state,
                    "image": c.image,
                    "update": c.update_available,
                    "cpu": c.cpu_percent,
                    "memory": c.memory_bytes,
                }
                for c in listed[:50]
            ],
            "notices": [asdict(n) for n in report.notices[:10]],
        }
        return WidgetPayload("available", as_of=utc_now(self.clock), data=data)


def register_host_widgets(
    registry: Any, capabilities: CapabilityRegistry, clock: Clock | None = None
) -> None:
    reports = HostReports(capabilities)
    for definition, provider in (
        (HOST, HostProvider(reports, clock)),
        (STORAGE, StorageProvider(reports, clock)),
        (CONTAINERS, ContainersProvider(reports, clock)),
    ):
        if registry.get(definition.key) is None:
            registry.register(definition, provider, owner=OWNER)
