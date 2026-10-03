"""Campaigns module facade (spec 014): definitions and versions, occurrence planning, activation intervals
and the reconciler, manual overrides, the active resolver, condition matching, and the ports other modules
consume — ``economy.modifiers`` and ``economy.definition_sources`` (013), ``campaigns.reader`` (009/017),
``campaigns.content``, the ``campaign`` calendar source (011) and the ``campaigns.active`` widget (009)."""

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from portalab.capabilities.campaigns import CONTENT, READER
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.content import CalendarSourceRegistry, default_calendar_sources
from portalab.capabilities.dashboard import WidgetRegistry, default_widgets
from portalab.capabilities.economy import DEFINITION_SOURCES, MODIFIERS
from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.capabilities.i18n import TIME
from portalab.capabilities.notifications import declare_category, default_categories
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.time import Clock, utc_now
from portalab.modules.campaigns import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.campaigns.content.provider import CampaignContent
from portalab.modules.campaigns.definitions.service import Definitions
from portalab.modules.campaigns.events import register_event_types
from portalab.modules.campaigns.integrations import ACTIVE_WIDGET, ActiveWidget
from portalab.modules.campaigns.intervals.manager import Intervals
from portalab.modules.campaigns.matching.conditions import Matcher
from portalab.modules.campaigns.modifiers.provider import CampaignModifiers
from portalab.modules.campaigns.observability import log, metrics
from portalab.modules.campaigns.overrides.service import Overrides
from portalab.modules.campaigns.planner.planner import Resolve, resolve_wall_clock
from portalab.modules.campaigns.presentation.service import Presentation
from portalab.modules.campaigns.resolver.active import ActiveResolver
from portalab.modules.campaigns.scheduler.reconciler import Reconciler
from portalab.modules.campaigns.settings import SETTINGS, CampaignsConfig

OWNER = "module:campaigns"
INSTANCE = "campaigns"
RECONCILE_JOB = "campaigns.reconcile"
ANNOUNCEMENT = "campaigns.announcement"


class CampaignsModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
        event_types: EventTypeRegistry = default_event_types,
        widgets: WidgetRegistry = default_widgets,
        observables: ObservableRegistry = default_observables,
        calendar_sources: CalendarSourceRegistry = default_calendar_sources,
    ) -> None:
        self.database = database
        self.audit = audit
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.event_types = event_types
        self.widgets = widgets
        self.observables = observables
        self.calendar_sources = calendar_sources
        self.config = CampaignsConfig()
        self.intervals = Intervals(events)
        self.definitions = Definitions(
            database, audit, self.intervals, capabilities, resolve=self.resolver_fn, clock=clock
        )
        self.reconciler = Reconciler(database, self.intervals, lambda: self.config, clock=clock)
        self.overrides = Overrides(database, audit, self.reconciler, clock=clock)
        self.resolver = ActiveResolver(database)
        self.matcher = Matcher(capabilities, database, clock=clock)
        self.modifiers = CampaignModifiers(self.resolver, self.matcher)
        self.simulation = CampaignModifiers(
            self.resolver, Matcher(capabilities, database, record_failures=False, clock=clock)
        )
        self.content = CampaignContent(self.resolver)
        self.presentation = Presentation(
            database, self.resolver, self.matcher, capabilities, authorizer, clock=clock
        )

    def resolver_fn(self) -> Resolve:
        """026 ``resolve_wall_clock`` (portal DST policy) when Internationalization is present."""
        providers = self.capabilities.system_providers(TIME)
        if not providers:
            return resolve_wall_clock
        port = providers[0].provider

        def resolve(local: datetime, time_zone: str) -> datetime:
            return port.resolve_wall_clock(local, time_zone)  # type: ignore[no-any-return]

        return resolve

    def register(self) -> None:
        register_event_types(self.event_types)
        for name, provider in (
            (MODIFIERS, self.modifiers),
            (DEFINITION_SOURCES, self.content),
            (READER, self.presentation),
            (CONTENT, self.content),
        ):
            registered = self.capabilities.system_providers(name)
            mine = any(p.instance_ref == INSTANCE for p in registered)
            if not mine and (
                not registered or name in (MODIFIERS, DEFINITION_SOURCES)
            ):  # multi-provider ports
                self.capabilities.provide(name, provider, instance_ref=INSTANCE, owner=OWNER)
        if self.calendar_sources.get("campaign") is None:
            self.calendar_sources.register(self.presentation, owner=OWNER)
        if self.widgets.get(ACTIVE_WIDGET.key) is None:
            self.widgets.register(ACTIVE_WIDGET, _widget(self), owner=OWNER)
        if default_categories.get(ANNOUNCEMENT) is None:
            declare_category(ANNOUNCEMENT, OWNER, "campaigns:category.announcement")
        self.observables.declare(
            ObservedComponent(
                "campaigns",
                OWNER,
                label="Campaigns",
                functional_checks=(Check("schedule", self.probe),),
                metrics=("campaigns.boundary_late", "campaigns.attributes.unavailable"),
            )
        )

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def reconcile() -> None:
            await self.reconciler.run()

        return [
            self.start,
            register_periodic(
                jobs, self.database, RECONCILE_JOB, timedelta(seconds=60), reconcile, owner=OWNER
            ),
        ]

    async def start(self) -> None:
        await self.refresh_config()

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                values = {
                    name: (await providers[0].provider.get(key)).value for name, key in SETTINGS.items()
                }
                self.config = replace(self.config, **values)
        except Exception:
            log.warning("campaigns configuration not refreshed")

    async def probe(self) -> CheckResult:
        active = await self.resolver.at(utc_now(self.clock))
        facts = {
            "active": len(active),
            "late_boundaries": metrics.snapshot().get("campaigns.boundary_late", 0),
        }
        if len(active) > self.config.max_active_campaigns:
            return CheckResult("degraded", "more active campaigns than recommended", facts)
        return CheckResult("ok", "schedule reconciled", facts)


def _widget(module: CampaignsModule) -> ActiveWidget:
    return ActiveWidget(module.presentation, module.clock)
