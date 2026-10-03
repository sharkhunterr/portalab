"""Support module facade — Slice A: incidents (spec 016)."""

from typing import Any

from sqlalchemy import func, select

from portalab.capabilities.dashboard import WidgetRegistry, default_widgets
from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.capabilities.health import INCIDENTS, SERVICE_DIRECTORY
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import SearchRegistry, default_search
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock
from portalab.modules.support import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.support import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.support.events import register_event_types
from portalab.modules.support.incidents.integrations import (
    OPEN_INCIDENTS,
    IncidentSearchProvider,
    OpenIncidentsWidget,
)
from portalab.modules.support.incidents.notify import IncidentNotifier
from portalab.modules.support.incidents.port import IncidentsPort
from portalab.modules.support.incidents.service import OPEN_STATES, IncidentService
from portalab.modules.support.models import Incident
from portalab.modules.support.settings import SupportConfig

OWNER = "module:support"


class SupportModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
        widgets: WidgetRegistry = default_widgets,
        search: SearchRegistry = default_search,
        event_types: EventTypeRegistry = default_event_types,
        observables: ObservableRegistry = default_observables,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.config = SupportConfig()
        self.notifier = IncidentNotifier(capabilities)
        self.incidents = IncidentService(database, events, audit, clock=clock, on_change=self.notifier)
        self.port = IncidentsPort(self.incidents)
        self.widgets = widgets
        self.search = search
        self.event_types = event_types
        self.observables = observables

    def register(self) -> None:
        if not self.capabilities.system_providers(INCIDENTS):
            self.capabilities.provide(INCIDENTS, self.port, instance_ref="support", owner=OWNER)
        register_event_types(self.event_types)
        if self.widgets.get(OPEN_INCIDENTS.key) is None:
            self.widgets.register(
                OPEN_INCIDENTS, OpenIncidentsWidget(self.incidents, self.clock), owner=OWNER
            )
        if self.search.provider("incidents") is None:
            self.search.register(IncidentSearchProvider(self.incidents, self.authorizer), owner=OWNER)
        self.observables.declare(
            ObservedComponent(
                "support", OWNER, label="Support", functional_checks=(Check("incidents", self.probe),)
            )
        )

    async def service_names(self) -> dict[str, str]:
        try:
            providers = self.capabilities.system_providers(SERVICE_DIRECTORY)
            if not providers:
                return {}
            return {s.id: s.name for s in await providers[0].provider.services()}
        except Exception:
            return {}

    async def probe(self) -> CheckResult:
        async with self.database.session() as session:
            open_count = int(
                await session.scalar(
                    select(func.count()).select_from(Incident).where(Incident.state.in_(OPEN_STATES))
                )
                or 0
            )
        critical = 0
        async with self.database.session() as session:
            critical = int(
                await session.scalar(
                    select(func.count())
                    .select_from(Incident)
                    .where(Incident.state.in_(OPEN_STATES), Incident.severity == "critical")
                )
                or 0
            )
        facts: dict[str, Any] = {"open_incidents": open_count, "critical": critical}
        return CheckResult("ok", "incidents reachable", facts)
