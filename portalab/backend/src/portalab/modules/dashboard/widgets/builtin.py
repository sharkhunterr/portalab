"""First-party widgets (T013, T029): a static "welcome / next steps" widget and the services health summary
(state from Health 006 through ``health.service_state``, names from ``connectors.directory``), plus the
services ``ChangeSummaryProvider`` for "Since Last Login". Data comes only through capabilities."""

import asyncio
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from portalab.capabilities.dashboard import (
    ChangeItem,
    Refresh,
    Size,
    SizeLimits,
    WidgetDefinition,
    WidgetPayload,
    WidgetRegistry,
    WidgetUnavailable,
)
from portalab.capabilities.health import SERVICE_DIRECTORY, SERVICE_STATE
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.service_events import STATUS_CHANGED
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.time import Clock, utc_now

OWNER = "module:dashboard"
SERVICES_READ = "services.read"

WELCOME = WidgetDefinition(
    key="dashboard.welcome",
    owner=OWNER,
    title_key="dashboard:widget.welcome.title",
    description_key="dashboard:widget.welcome.description",
    icon="sparkles",
    required_permission="users.self.manage",
    size=SizeLimits(default=Size(6, 2), min=Size(3, 2), max=Size(12, 4)),
    component_id="dashboard.welcome",
)

SERVICES_SUMMARY = WidgetDefinition(
    key="health.services_summary",
    owner=OWNER,
    title_key="dashboard:widget.services.title",
    description_key="dashboard:widget.services.description",
    icon="server",
    required_permission=SERVICES_READ,
    config_schema={
        "type": "object",
        "properties": {
            "show": {"enum": ["all", "problems"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "additionalProperties": False,
    },
    config_defaults={"show": "all", "limit": 8},
    size=SizeLimits(default=Size(6, 2), min=Size(3, 2), max=Size(12, 6)),
    refresh=Refresh(mode="event", events=(STATUS_CHANGED,)),
    stale_after_s=600,
    template="status",
    component_id="health.services_summary",
)

SERVICE_LINKS = WidgetDefinition(
    key="health.service_links",
    owner=OWNER,
    title_key="dashboard:widget.links.title",
    description_key="dashboard:widget.links.description",
    icon="link",
    required_permission=SERVICES_READ,
    size=SizeLimits(default=Size(6, 3), min=Size(3, 2), max=Size(12, 6)),
    refresh=Refresh(mode="event", events=(STATUS_CHANGED,)),
    stale_after_s=600,
    component_id="health.service_links",
)

NEXT_STEPS: tuple[dict[str, str], ...] = (
    {"label_key": "nav.search", "route": "/search"},
    {"label_key": "nav.services", "route": "/services"},
    {"label_key": "nav.appearance", "route": "/settings/appearance"},
    {"label_key": "nav.language", "route": "/settings/language"},
)


class WelcomeProvider:
    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        return WidgetPayload(
            "available", as_of=utc_now(self.clock), data={"steps": [dict(s) for s in NEXT_STEPS]}
        )


def _provider(capabilities: CapabilityRegistry, name: str) -> Any | None:
    try:
        providers = capabilities.system_providers(name)
    except Exception:
        return None
    return providers[0].provider if providers else None


class ServicesSummaryProvider:
    def __init__(
        self, capabilities: CapabilityRegistry, authorizer: Authorizer, clock: Clock | None = None
    ) -> None:
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock

    async def _rows(self) -> list[dict[str, Any]]:
        states = _provider(self.capabilities, SERVICE_STATE)
        directory = _provider(self.capabilities, SERVICE_DIRECTORY)
        if states is None or directory is None:
            raise WidgetUnavailable("health is not available")
        views, services = await asyncio.gather(states.all(), directory.services())
        by_id = {view.service_id: view for view in views}
        rows = []
        for service in services:
            view = by_id.get(service.id)
            rows.append(
                {
                    "id": service.id,
                    "name": service.name,
                    "state": view.state if view else "unknown",
                    "since": view.since.isoformat() if view else None,
                    "as_of": view.as_of if view else None,
                }
            )
        return rows

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        rows = await self._rows()
        if not rows:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["state"]] = counts.get(row["state"], 0) + 1
        shown = [r for r in rows if config.get("show") != "problems" or r["state"] not in ("operational",)]
        oldest = min((r["as_of"] for r in rows if r["as_of"] is not None), default=None)
        unknown = [r["name"] for r in rows if r["state"] == "unknown"]
        items = [
            {
                "id": r["id"],
                "name": r["name"],
                "state": r["state"],
                "since": r["since"],
                "route": f"/services/{r['id']}",
            }
            for r in shown[: int(config.get("limit", 8))]
        ]
        return WidgetPayload(
            "partial" if unknown and len(unknown) < len(rows) else "available",
            as_of=oldest or utc_now(self.clock),
            data={"counts": counts, "items": items, "total": len(rows)},
            partial_reasons=("some services have no recent health data",)
            if unknown and len(unknown) < len(rows)
            else (),
        )


class ServiceLinksProvider(ServicesSummaryProvider):
    """027: the configured services as quick links — each one's public address (set by an administrator,
    or its https address) and its state; a service without an address leads to its status page."""

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        states = _provider(self.capabilities, SERVICE_STATE)
        directory = _provider(self.capabilities, SERVICE_DIRECTORY)
        if states is None or directory is None:
            raise WidgetUnavailable("health is not available")
        views, services = await asyncio.gather(states.all(), directory.services())
        by_id = {view.service_id: view for view in views}
        items = [
            {
                "id": service.id,
                "name": service.name,
                "connector": service.connector,
                "state": by_id[service.id].state if service.id in by_id else "unknown",
                "link": service.link,
                "route": f"/services/{service.id}",
            }
            for service in services
            if service.state != "disconnected"
        ]
        if not items:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        return WidgetPayload("available", as_of=utc_now(self.clock), data={"items": items})


class ServicesChanges:
    """Service state changes since the boundary, for principals holding ``services.read``."""

    kind = "services"

    def __init__(self, provider: ServicesSummaryProvider) -> None:
        self.provider = provider

    async def changes_since(
        self, principal: Principal, since: datetime, limit: int, ctx: LocaleContext
    ) -> Sequence[ChangeItem]:
        if not await self.provider.authorizer.is_allowed(principal, SERVICES_READ):
            return []
        items = []
        for row in await self.provider._rows():
            if row["since"] is None:
                continue
            at = datetime.fromisoformat(row["since"])
            if at <= since:
                continue
            items.append(
                ChangeItem(
                    kind=self.kind,
                    occurred_at=at,
                    ref=f"/services/{row['id']}",
                    title_key="dashboard:summary.serviceState",
                    title_args={"name": row["name"], "state": row["state"]},
                    priority=2 if row["state"] in ("unavailable", "degraded") else 1,
                )
            )
        items.sort(key=lambda item: item.occurred_at, reverse=True)
        return items[:limit]


def register_builtin(
    registry: WidgetRegistry,
    capabilities: CapabilityRegistry,
    authorizer: Authorizer,
    clock: Clock | None = None,
) -> None:
    registry.register(WELCOME, WelcomeProvider(clock), owner=OWNER)
    services = ServicesSummaryProvider(capabilities, authorizer, clock)
    registry.register(SERVICES_SUMMARY, services, owner=OWNER)
    if registry.get(SERVICE_LINKS.key) is None:
        registry.register(SERVICE_LINKS, ServiceLinksProvider(capabilities, authorizer, clock), owner=OWNER)
    registry.register_summary(ServicesChanges(services), owner=OWNER)
