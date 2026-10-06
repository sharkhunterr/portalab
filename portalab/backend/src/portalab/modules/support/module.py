"""Support module facade (spec 016): incidents (Slice A), tickets, feedback and diagnosis (Slice B)."""

from dataclasses import replace
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select

from portalab.capabilities.automation_actions import ActionRegistry, default_actions
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.content import default_calendar_sources
from portalab.capabilities.dashboard import WidgetRegistry, default_widgets
from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.capabilities.health import INCIDENTS, SERVICE_DIRECTORY
from portalab.capabilities.notifications import declare_category, default_categories
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.capabilities.search import SearchRegistry, default_search
from portalab.capabilities.support import TICKETS
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.logging import get_logger
from portalab.core.time import Clock
from portalab.modules.support import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.support import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.support.admin.definitions import Definitions
from portalab.modules.support.attachments.service import AttachmentService
from portalab.modules.support.conversion.service import ConversionService
from portalab.modules.support.diagnosis.orchestrator import DiagnosisOrchestrator
from portalab.modules.support.events import register_event_types
from portalab.modules.support.feedback.service import FeedbackService
from portalab.modules.support.incidents.integrations import (
    OPEN_INCIDENTS,
    IncidentCalendarSource,
    IncidentSearchProvider,
    OpenIncidentsWidget,
)
from portalab.modules.support.incidents.notify import CATEGORY, IncidentNotifier
from portalab.modules.support.incidents.port import IncidentsPort
from portalab.modules.support.incidents.service import OPEN_STATES, IncidentService
from portalab.modules.support.models import Incident, Ticket
from portalab.modules.support.participant import SupportParticipant
from portalab.modules.support.precheck.service import Precheck
from portalab.modules.support.settings import SETTINGS, SupportConfig
from portalab.modules.support.summary import SupportChanges
from portalab.modules.support.tickets.integrations import (
    ACTIONS,
    MY_TICKETS,
    QUEUE,
    FeedbackSearchProvider,
    TicketSearchProvider,
    TicketsWidget,
    register_actions,
)
from portalab.modules.support.tickets.notify import ASSIGNMENT, FEEDBACK, STATUS, SupportNotifier
from portalab.modules.support.tickets.service import TicketService, TicketsPortImpl

OWNER = "module:support"
DRAFTS_JOB = "support.drafts_purge"
log = get_logger("portalab.support")


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
        actions: ActionRegistry = default_actions,
        blobs: BlobStore | None = None,
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
        self.actions = actions
        self.blobs = blobs
        self.audit = audit
        self.definitions = Definitions(database, audit, clock=clock)
        self.ticket_notifier = SupportNotifier(capabilities)
        self.tickets = TicketService(
            database,
            events,
            audit,
            authorizer,
            capabilities,
            self.definitions,
            lambda: self.config,
            self.ticket_notifier,
            clock=clock,
        )
        self.attachments = AttachmentService(self.tickets, blobs, capabilities, lambda: self.config)
        self.precheck = Precheck(self.incidents, capabilities, authorizer, lambda: self.config)
        self.feedback = FeedbackService(database, events, authorizer, self.definitions, clock=clock)
        self.feedback.notifier = self.ticket_notifier
        self.conversion = ConversionService(self.tickets, events, capabilities, authorizer, clock=clock)
        self.diagnosis = DiagnosisOrchestrator(
            database, capabilities, self.precheck, lambda: self.config, clock=clock
        )

    def register(self) -> None:
        if not self.capabilities.system_providers(INCIDENTS):
            self.capabilities.provide(INCIDENTS, self.port, instance_ref="support", owner=OWNER)
        register_event_types(self.event_types)
        if default_categories.get(CATEGORY) is None:
            declare_category(
                CATEGORY,
                OWNER,
                "support:category.incident",
                default_priority="high",
                default_channels=("portal", "email"),
            )
        if not self.capabilities.system_providers(TICKETS):
            self.capabilities.provide(
                TICKETS, TicketsPortImpl(self.tickets), instance_ref="support", owner=OWNER
            )
        participant = SupportParticipant(self.database, self.blobs)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == "support" for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref="support", owner=OWNER)
        months = lambda: timedelta(days=31 * max(1, self.config.ticket_retention_months))  # noqa: E731
        for name, table, column in (
            ("support.tickets", "support.tickets", "closed_at"),
            ("support.feedback", "support.feedback_items", "created_at"),
        ):
            default_retention_targets.register(
                RetentionTarget(name, table, "personal", column, "anonymize", OWNER, window=months)
            )
        for key, label, channels in (
            (ASSIGNMENT, "support:category.assignment", ("portal", "email")),
            (STATUS, "support:category.ticket_status", ("portal", "email")),
            (FEEDBACK, "support:category.feedback", ("portal",)),
        ):
            if default_categories.get(key) is None:
                declare_category(key, OWNER, label, default_channels=channels)
        for definition, queue in ((MY_TICKETS, False), (QUEUE, True)):
            if self.widgets.get(definition.key) is None:
                self.widgets.register(definition, TicketsWidget(self.tickets, queue, self.clock), owner=OWNER)
        if not any(p.kind == "support" for p in self.widgets.summaries()):  # 027: since your last visit
            self.widgets.register_summary(SupportChanges(self.database), owner=OWNER)
        if self.search.provider("tickets") is None:
            self.search.register(TicketSearchProvider(self.tickets), owner=OWNER)
            self.search.register(FeedbackSearchProvider(self.tickets), owner=OWNER)
            for action in ACTIONS:
                self.search.register_action(action, owner=OWNER)
        register_actions(self.tickets, self.incidents, self.actions)
        if self.widgets.get(OPEN_INCIDENTS.key) is None:
            self.widgets.register(
                OPEN_INCIDENTS, OpenIncidentsWidget(self.incidents, self.clock), owner=OWNER
            )
        if self.search.provider("incidents") is None:
            self.search.register(IncidentSearchProvider(self.incidents, self.authorizer), owner=OWNER)
        if default_calendar_sources.get(IncidentCalendarSource.kind) is None:  # 027: incidents that last
            default_calendar_sources.register(IncidentCalendarSource(self.incidents, self.clock), owner=OWNER)
        self.observables.declare(
            ObservedComponent(
                "support", OWNER, label="Support", functional_checks=(Check("incidents", self.probe),)
            )
        )

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def purge() -> None:
            await self.diagnosis.purge()

        return [
            self.start,
            register_periodic(jobs, self.database, DRAFTS_JOB, timedelta(hours=1), purge, owner=OWNER),
        ]

    async def start(self) -> None:
        await self.refresh_config()
        await self.definitions.ensure_baseline()

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                values = {
                    name: (await providers[0].provider.get(key)).value for name, key in SETTINGS.items()
                }
                self.config = replace(self.config, **values)
        except Exception:
            log.warning("support configuration not refreshed")

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
        async with self.database.session() as session:
            waiting = int(
                await session.scalar(
                    select(func.count()).select_from(Ticket).where(Ticket.state.in_(("open", "in_progress")))
                )
                or 0
            )
        facts: dict[str, Any] = {"open_incidents": open_count, "critical": critical, "open_tickets": waiting}
        return CheckResult("ok", "incidents reachable", facts)
