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
    with_styles,
)
from portalab.capabilities.health import SERVICE_DIRECTORY, SERVICE_STATE, watched
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.service_events import STATUS_CHANGED
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.dashboard.widgets.hosts import register_host_widgets

OWNER = "module:dashboard"
SERVICES_READ = "services.read"

WELCOME = WidgetDefinition(
    key="dashboard.welcome",
    owner=OWNER,
    title_key="dashboard:widget.welcome.title",
    description_key="dashboard:widget.welcome.description",
    icon="sparkles",
    required_permission="users.self.manage",
    size=SizeLimits(default=Size(6, 2), min=Size(3, 1), max=Size(12, 4)),
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
    size=SizeLimits(default=Size(6, 2), min=Size(3, 1), max=Size(12, 6)),  # 027: one row = compact
    refresh=Refresh(mode="event", events=(STATUS_CHANGED,)),
    stale_after_s=600,
    template="status",
    component_id="health.services_summary",
)

# 027: the same states in one line — a dot per service and the count that works (a header-sized block)
SERVICES_COMPACT = WidgetDefinition(
    key="health.services_compact",
    owner=OWNER,
    title_key="dashboard:widget.services_compact.title",
    description_key="dashboard:widget.services_compact.description",
    icon="activity",
    required_permission=SERVICES_READ,
    config_schema={"type": "object", "properties": {}, "additionalProperties": False},
    config_defaults={"_hide_title": True},
    size=SizeLimits(default=Size(4, 1), min=Size(2, 1), max=Size(12, 2)),
    refresh=Refresh(mode="event", events=(STATUS_CHANGED,)),
    stale_after_s=600,
    component_id="health.services_compact",
)

SERVICE_LINKS = WidgetDefinition(
    key="health.service_links",
    owner=OWNER,
    title_key="dashboard:widget.links.title",
    description_key="dashboard:widget.links.description",
    icon="link",
    required_permission=SERVICES_READ,
    size=SizeLimits(default=Size(6, 3), min=Size(3, 1), max=Size(12, 6)),
    refresh=Refresh(mode="event", events=(STATUS_CHANGED,)),
    stale_after_s=600,
    component_id="health.service_links",
)

# 027: one service's state as on the services page — its badge, its last 48 hours as bars, its address
SERVICE_STATUS = WidgetDefinition(
    key="health.service_status",
    owner=OWNER,
    title_key="dashboard:widget.service_status.title",
    description_key="dashboard:widget.service_status.description",
    icon="activity",
    required_permission=SERVICES_READ,
    config_schema={
        "type": "object",
        # « x-options »: the settings offer the services by name (the value is the service's id)
        "properties": {"service": {"type": "string", "maxLength": 64, "x-options": "services"}},
        "additionalProperties": False,
    },
    config_defaults={"service": ""},
    size=SizeLimits(default=Size(4, 2), min=Size(3, 1), max=Size(12, 4)),
    refresh=Refresh(mode="event", events=(STATUS_CHANGED,)),
    stale_after_s=600,
    component_id="health.service_status",
    multiple=True,
)

# 027: « since your last visit » as a widget a member places (and hides) like the others
SINCE_LAST_VISIT = WidgetDefinition(
    key="dashboard.since_last_visit",
    owner=OWNER,
    title_key="dashboard:widget.since_last_visit.title",
    description_key="dashboard:widget.since_last_visit.description",
    icon="sparkles",
    required_permission="users.self.manage",
    size=SizeLimits(default=Size(12, 3), min=Size(3, 1), max=Size(12, 8)),
    stale_after_s=300,
    component_id="dashboard.since_last_visit",
)

# 027: one-cell tiles — a shortcut (an icon that opens a page or a link) and a single value
SHORTCUTS: dict[str, tuple[str, str]] = {  # destination → (route, icon); labels « dashboard:shortcut.<key> »
    "media": ("/media", "film"),
    "browse": ("/media/browse", "library"),
    "requests": ("/media/requests", "inbox"),
    "discover": ("/discover", "compass"),
    "marketplace": ("/marketplace", "shop"),
    "progression": ("/progression", "trophy"),
    "community": ("/community", "users"),
    "calendar": ("/calendar", "calendar"),
    "news": ("/news", "newspaper"),
    "wiki": ("/wiki", "book"),
    "support": ("/support", "lifebuoy"),
    "new_ticket": ("/support/new", "ticket"),
    "services": ("/services", "server"),
    "incidents": ("/incidents", "alert"),
    "search": ("/search", "search"),
    "notifications": ("/notifications", "bell"),
    "appearance": ("/settings/appearance", "palette"),
    "link": ("", "link"),
}
SHORTCUT = WidgetDefinition(
    key="dashboard.shortcut",
    owner=OWNER,
    title_key="dashboard:widget.shortcut.title",
    description_key="dashboard:widget.shortcut.description",
    icon="link",
    required_permission="users.self.manage",
    config_schema={
        "type": "object",
        "properties": {
            "destination": {"enum": list(SHORTCUTS)},
            "url": {"type": "string", "maxLength": 300},
            "label": {"type": "string", "maxLength": 24},
        },
        "additionalProperties": False,
    },
    config_defaults={"destination": "media", "url": "", "label": ""},
    size=SizeLimits(default=Size(1, 1), min=Size(1, 1), max=Size(3, 2)),
    multiple=True,  # as many shortcuts as a member wants
    component_id="dashboard.shortcut",
)
VALUES = ("level", "coins", "contribution", "achievements", "unread", "incidents", "requests_left")
VALUE = WidgetDefinition(
    key="dashboard.value",
    owner=OWNER,
    title_key="dashboard:widget.value.title",
    description_key="dashboard:widget.value.description",
    icon="gauge",
    required_permission="users.self.manage",
    config_schema={
        "type": "object",
        "properties": {"metric": {"enum": list(VALUES)}},
        "additionalProperties": False,
    },
    config_defaults={"metric": "level"},
    size=SizeLimits(default=Size(1, 1), min=Size(1, 1), max=Size(3, 2)),
    multiple=True,
    component_id="dashboard.value",
)

# 027: progress of something of mine as a bar — across (``progress``) or upright (``progress_vertical``)
PROGRESS_METRICS = ("level", "objectives", "quests", "achievements")
_PROGRESS_SCHEMA = {
    "type": "object",
    "properties": {"metric": {"enum": list(PROGRESS_METRICS)}},
    "additionalProperties": False,
}
PROGRESS = WidgetDefinition(
    key="dashboard.progress",
    owner=OWNER,
    title_key="dashboard:widget.progress.title",
    description_key="dashboard:widget.progress.description",
    icon="gauge",
    required_permission="users.self.manage",
    config_schema=_PROGRESS_SCHEMA,
    config_defaults={"metric": "level", "_hide_title": True},
    size=SizeLimits(default=Size(4, 1), min=Size(2, 1), max=Size(12, 2)),
    multiple=True,
    component_id="dashboard.progress",
)
PROGRESS_VERTICAL = WidgetDefinition(
    key="dashboard.progress_vertical",
    owner=OWNER,
    title_key="dashboard:widget.progress_vertical.title",
    description_key="dashboard:widget.progress_vertical.description",
    icon="chart",
    required_permission="users.self.manage",
    config_schema=_PROGRESS_SCHEMA,
    config_defaults={"metric": "level", "_hide_title": True},
    size=SizeLimits(default=Size(1, 2), min=Size(1, 2), max=Size(3, 6)),
    multiple=True,
    component_id="dashboard.progress_vertical",
)
# 027: layout helpers — a separator (a line, dots, a gradient or just space, with an optional label)
SEPARATOR = WidgetDefinition(
    key="dashboard.separator",
    owner=OWNER,
    title_key="dashboard:widget.separator.title",
    description_key="dashboard:widget.separator.description",
    icon="minus",
    required_permission="users.self.manage",
    config_schema={
        "type": "object",
        "properties": {
            "style": {"enum": ["line", "dashed", "dotted", "gradient", "space"]},
            "label": {"type": "string", "maxLength": 40},
        },
        "additionalProperties": False,
    },
    # the raw line on the page: no box, no title (both can be turned back on in its settings)
    config_defaults={"style": "gradient", "label": "", "_hide_title": True, "_no_box": True},
    size=SizeLimits(default=Size(12, 1), min=Size(1, 1), max=Size(12, 2)),
    multiple=True,
    component_id="dashboard.separator",
)
CLOCK = WidgetDefinition(
    key="dashboard.clock",
    owner=OWNER,
    title_key="dashboard:widget.clock.title",
    description_key="dashboard:widget.clock.description",
    icon="clock",
    required_permission="users.self.manage",
    config_schema={
        "type": "object",
        "properties": {"seconds": {"type": "boolean"}, "date": {"type": "boolean"}},
        "additionalProperties": False,
    },
    config_defaults={"seconds": False, "date": True, "_hide_title": True},
    size=SizeLimits(default=Size(2, 1), min=Size(1, 1), max=Size(6, 3)),
    multiple=True,
    component_id="dashboard.clock",
)
NOTE = WidgetDefinition(
    key="dashboard.note",
    owner=OWNER,
    title_key="dashboard:widget.note.title",
    description_key="dashboard:widget.note.description",
    icon="feather",
    required_permission="users.self.manage",
    config_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "maxLength": 280},
            "color": {"enum": ["yellow", "pink", "blue", "green", "violet"]},
        },
        "additionalProperties": False,
    },
    config_defaults={"text": "", "color": "yellow", "_hide_title": True, "_no_box": True},
    size=SizeLimits(default=Size(3, 2), min=Size(2, 1), max=Size(6, 4)),
    multiple=True,
    component_id="dashboard.note",
)
COUNTDOWN = WidgetDefinition(
    key="dashboard.countdown",
    owner=OWNER,
    title_key="dashboard:widget.countdown.title",
    description_key="dashboard:widget.countdown.description",
    icon="hourglass",
    required_permission="users.self.manage",
    config_schema={
        "type": "object",
        "properties": {
            "label": {"type": "string", "maxLength": 40},
            "date": {"type": "string", "format": "date", "pattern": "^(\\d{4}-\\d{2}-\\d{2})?$"},
        },
        "additionalProperties": False,
    },
    config_defaults={"label": "", "date": "", "_hide_title": True},
    size=SizeLimits(default=Size(2, 1), min=Size(1, 1), max=Size(6, 2)),
    multiple=True,
    component_id="dashboard.countdown",
)
# 027: compact widgets show their content alone by default (the title can be turned back on)
# what the member set is the content: an empty note or a countdown without a date says « set me up »
NEEDS = {NOTE.key: "text", COUNTDOWN.key: "date"}

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


class SinceLastVisitProvider:
    """027: what changed for me since my last visit (the dashboard's own summary)."""

    def __init__(self, summary: Any, clock: Clock | None = None) -> None:
        self.summary = summary
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        found = await self.summary.summary(principal, ctx)
        items = [
            {
                "kind": i.kind,
                "occurred_at": i.occurred_at.isoformat(),
                "ref": i.ref,
                "title": i.title,
                "title_key": i.title_key,
                "title_args": dict(i.title_args),
                "priority": i.priority,
                "detail": i.detail,
            }
            for i in found.items
        ]
        data = {"since": found.since.isoformat(), "items": items, "unavailable": list(found.unavailable)}
        return WidgetPayload("available" if items else "no-data", as_of=utc_now(self.clock), data=data)


class ShortcutProvider:
    """027: a one-cell shortcut — a page of the portal, or an https link of the member's choice."""

    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        destination = str(config.get("destination") or "media")
        route, icon = SHORTCUTS.get(destination, SHORTCUTS["media"])
        url = str(config.get("url") or "").strip()
        if destination == "link" and not url.startswith("https://"):
            return WidgetPayload("no-data", as_of=utc_now(self.clock), data={"destination": destination})
        data = {
            "destination": destination,
            "route": route or None,
            "href": url if destination == "link" else None,
            "icon": icon,
            "label": str(config.get("label") or "").strip() or None,
        }
        return WidgetPayload("available", as_of=utc_now(self.clock), data=data)


class ValueProvider:
    """027: a one-cell value; the interface reads it where the portal already shows it (progression,
    notifications, incidents, requests) so it stays in step with the header."""

    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        metric = str(config.get("metric") or "level")
        return WidgetPayload(
            "available", as_of=utc_now(self.clock), data={"metric": metric if metric in VALUES else "level"}
        )


class SettingsProvider:
    """027: widgets drawn from their own settings (progress, separator, clock, note, countdown) — the
    interface reads the values it shows where the portal already shows them."""

    def __init__(self, key: str, clock: Clock | None = None) -> None:
        self.key = key
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        data = {k: v for k, v in config.items() if not k.startswith("_")}
        needed = NEEDS.get(self.key)
        if needed and not str(data.get(needed) or "").strip():
            return WidgetPayload("no-data", as_of=utc_now(self.clock), data=data)
        return WidgetPayload("available", as_of=utc_now(self.clock), data=data)


def _provider(capabilities: CapabilityRegistry, name: str) -> Any | None:
    try:
        providers = capabilities.system_providers(name)
    except Exception:
        return None
    return providers[0].provider if providers else None


class ServicesSummaryProvider:
    def __init__(
        self,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        clock: Clock | None = None,
        *,
        compact: bool = False,
    ) -> None:
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.compact = compact  # 027: every service, for the one-line version

    async def _rows(self) -> list[dict[str, Any]]:
        states = _provider(self.capabilities, SERVICE_STATE)
        directory = _provider(self.capabilities, SERVICE_DIRECTORY)
        if states is None or directory is None:
            raise WidgetUnavailable("health is not available")
        views, services = await asyncio.gather(states.all(), directory.services())
        by_id = {view.service_id: view for view in views}
        rows = []
        for service in services:
            if not watched(service):
                continue  # switched off: not watched, so neither unknown nor « a source did not answer »
            view = by_id.get(service.id)
            rows.append(
                {
                    "id": service.id,
                    "name": service.name,
                    "connector": service.connector,
                    "importance": service.importance,
                    "state": view.state if view else "unknown",
                    "since": view.since.isoformat() if view else None,
                    "availability": view.availability if view else None,
                    "as_of": view.as_of if view else None,
                    "link": service.link,
                }
            )
        # 027: trouble first, then by importance, then by name
        severity = {"unavailable": 0, "degraded": 1, "maintenance": 2, "unknown": 3, "operational": 4}
        order = {"critical": 0, "major": 1, "minor": 2, "internal": 3}
        rows.sort(key=lambda r: (severity.get(r["state"], 5), order.get(r["importance"], 4), r["name"]))
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
                "connector": r["connector"],
                "importance": r["importance"],
                "state": r["state"],
                "since": r["since"],
                "availability": r["availability"],
                "route": f"/services/{r['id']}",
            }
            for r in shown[: int(config.get("limit", 50 if self.compact else 8))]
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
            if watched(service)
        ]
        if not items:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        return WidgetPayload("available", as_of=utc_now(self.clock), data={"items": items})


class ServiceStatusProvider(ServicesSummaryProvider):
    """027: the chosen service (by id) — by default the one that needs looking at most (trouble first,
    then the most important)."""

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        rows = await self._rows()
        if not rows:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        wanted = str(config.get("service") or "")
        row = next((r for r in rows if str(r["id"]) == wanted), rows[0])
        item = {
            "id": str(row["id"]),
            "name": row["name"],
            "connector": row["connector"],
            "state": row["state"],
            "availability": row["availability"],
            "link": row["link"],
            "route": f"/services/{row['id']}",
        }
        return WidgetPayload("available", as_of=row["as_of"] or utc_now(self.clock), data={"item": item})


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
        # 027: a service in trouble now is news on its own; the ones back to normal make one line
        items: list[ChangeItem] = []
        recovered: list[tuple[datetime, str]] = []
        for row in await self.provider._rows():
            if row["since"] is None:
                continue
            at = datetime.fromisoformat(row["since"])
            if at <= since:
                continue
            if row["state"] in ("unavailable", "degraded"):
                items.append(
                    ChangeItem(
                        kind=self.kind,
                        occurred_at=at,
                        ref=f"/services/{row['id']}",
                        title_key="dashboard:summary.serviceState",
                        title_args={"name": row["name"], "state": row["state"]},
                        priority=4,
                    )
                )
            else:
                recovered.append((at, str(row["name"])))
        if recovered:
            recovered.sort(reverse=True)
            items.append(
                ChangeItem(
                    kind=self.kind,
                    occurred_at=recovered[0][0],
                    ref="/services",
                    title_key="dashboard:summary.servicesBack",
                    title_args={"count": len(recovered)},
                    detail=", ".join(name for _, name in recovered[:6]),
                    priority=0,
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
    register_host_widgets(registry, capabilities, clock)  # #49/#50: servers (Glances, Unraid)
    services = ServicesSummaryProvider(capabilities, authorizer, clock)
    registry.register(SERVICES_SUMMARY, services, owner=OWNER)
    if registry.get(SERVICES_COMPACT.key) is None:
        registry.register(
            SERVICES_COMPACT,
            ServicesSummaryProvider(capabilities, authorizer, clock, compact=True),
            owner=OWNER,
        )
    if registry.get(SERVICE_LINKS.key) is None:
        registry.register(SERVICE_LINKS, ServiceLinksProvider(capabilities, authorizer, clock), owner=OWNER)
    if registry.get(SERVICE_STATUS.key) is None:
        registry.register(SERVICE_STATUS, ServiceStatusProvider(capabilities, authorizer, clock), owner=OWNER)
    registry.register_summary(ServicesChanges(services), owner=OWNER)
    for definition, provider in ((SHORTCUT, ShortcutProvider(clock)), (VALUE, ValueProvider(clock))):
        if registry.get(definition.key) is None:
            registry.register(definition, provider, owner=OWNER)
    for definition in (PROGRESS, PROGRESS_VERTICAL, SEPARATOR, CLOCK, NOTE, COUNTDOWN):
        if registry.get(definition.key) is None:
            registry.register(definition, SettingsProvider(definition.key, clock), owner=OWNER)


def register_since_last_visit(registry: WidgetRegistry, summary: Any, clock: Clock | None = None) -> None:
    if registry.get(SINCE_LAST_VISIT.key) is None:
        registry.register(SINCE_LAST_VISIT, SinceLastVisitProvider(summary, clock), owner=OWNER)


SERVICES_SUMMARY = with_styles(SERVICES_SUMMARY, "pulse")  # 027 (#31)
CLOCK = with_styles(CLOCK, "analog")  # 027 (#31)
COUNTDOWN = with_styles(COUNTDOWN, "flip")  # 027 (#31)
