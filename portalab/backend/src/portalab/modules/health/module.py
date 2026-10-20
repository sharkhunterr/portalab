"""Health module facade (spec 006): state derivation, probes, rollups, maintenance, infrastructure,
operations and the service detail sections."""

from datetime import timedelta
from typing import Any

from portalab.capabilities.administration import AdminSurface, default_admin_surfaces
from portalab.capabilities.ai import AIToolRegistry, default_ai_tools
from portalab.capabilities.content import default_calendar_sources
from portalab.capabilities.health import INFRA_HISTORY, SERVICE_STATE
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.service_signals import default_signals
from portalab.core.audit_port import AuditSink
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.time import Clock
from portalab.modules.health import event_types as _event_types  # noqa: F401 — registers event types
from portalab.modules.health import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.health.ai_tools import HealthAiTools
from portalab.modules.health.calendar_source import MaintenanceCalendarSource
from portalab.modules.health.detail.assembler import DetailAssembler
from portalab.modules.health.detail.history import HistoryQuery
from portalab.modules.health.detail.incidents import IncidentLinkService
from portalab.modules.health.infra.hosts import HostService
from portalab.modules.health.infra.service import InfraHistoryService, InfraMetricsService
from portalab.modules.health.infra.signals import register_host_signals
from portalab.modules.health.maintenance.service import END_JOB, START_JOB, MaintenanceService
from portalab.modules.health.operations.service import OperationsService
from portalab.modules.health.permissions import SERVICES_READ
from portalab.modules.health.probes.runner import ProbeRunner
from portalab.modules.health.probes.scheduler import ProbeScheduler
from portalab.modules.health.retention import register_targets
from portalab.modules.health.rollups.job import RollupJob
from portalab.modules.health.settings import HealthConfig
from portalab.modules.health.state.capability import ServiceStateReaderImpl
from portalab.modules.health.state.service import StateService

OWNER = "module:health"


class HealthModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        *,
        config: HealthConfig | None = None,
        clock: Clock | None = None,
        ai_tools: AIToolRegistry = default_ai_tools,
    ) -> None:
        self.ai_tools = ai_tools  # issue 171: the assistant's maintenance tool
        self.database = database
        self.capabilities = capabilities
        self.state = StateService(database, events, capabilities, config=config, clock=clock)
        self.runner = ProbeRunner(self.state)
        self.maintenance = MaintenanceService(self.state, audit)
        self.scheduler = ProbeScheduler(self.runner, self.maintenance)
        self.rollups = RollupJob(database, clock=clock)
        self.history = HistoryQuery(self.state)
        self.incidents = IncidentLinkService(self.state)
        self.infra = InfraMetricsService(self.state)
        self.scheduler.infra = self.infra  # #52: the metrics sampled with each sweep, for the charts
        self.infra_history = InfraHistoryService(self.infra)
        self.hosts = HostService(self.state)  # #49/#50: servers (Glances, Unraid)
        self.operations = OperationsService(self.state, audit)
        self.detail = DetailAssembler(
            self.state, self.maintenance, self.history, self.incidents, self.infra, self.operations
        )
        self.reader = ServiceStateReaderImpl(self.state)

    @property
    def config(self) -> HealthConfig:
        return self.state.config

    @config.setter
    def config(self, value: HealthConfig) -> None:
        self.state.config = value

    def register_capabilities(self) -> None:
        HealthAiTools(self, self.state.clock).register(self.ai_tools)
        self.capabilities.provide(SERVICE_STATE, self.reader, instance_ref="health", owner=OWNER)
        self.capabilities.provide(INFRA_HISTORY, self.infra_history, instance_ref="health", owner=OWNER)
        default_admin_surfaces.register(
            AdminSurface("health", "admin.surface.health", "/services", SERVICES_READ, OWNER)
        )
        register_targets(lambda: self.config)
        register_host_signals(self.hosts, default_signals)  # issue 122: a server's data, for automations
        if default_calendar_sources.get("maintenance") is None:  # spec 011: maintenance in the calendar
            default_calendar_sources.register(
                MaintenanceCalendarSource(self.database, clock=self.state.clock), owner=OWNER
            )

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def start(payload: dict[str, Any]) -> None:
            await self.maintenance.handle_job(payload, "started")

        async def end(payload: dict[str, Any]) -> None:
            await self.maintenance.handle_job(payload, "ended")

        jobs.register(START_JOB, start, idempotency="reconciles windows against the clock", owner=OWNER)
        jobs.register(END_JOB, end, idempotency="reconciles windows against the clock", owner=OWNER)
        sweep = self.scheduler.register(jobs)
        rollup = register_periodic(
            jobs, self.database, "health.rollup", timedelta(hours=1), self.rollups.run, owner=OWNER
        )
        return [sweep, rollup, self.start]

    async def start(self) -> None:
        """Start-up reconciliation: missed maintenance transitions and re-derived states."""
        await self.scheduler.ensure_partitions()
        await self.maintenance.reconcile()
        await self.state.evaluate_all()
