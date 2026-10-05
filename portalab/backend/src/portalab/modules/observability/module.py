"""Observability module facade (spec 025)."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from portalab.capabilities.administration import (
    PANEL_CAPABILITY,
    REQUIRED_ACTION_CAPABILITY,
    AdminSurface,
    default_admin_surfaces,
)
from portalab.capabilities.observability import (
    OBSERVABILITY_HEALTH,
    ObservableRegistry,
    default_observables,
)
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditSink
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.metrics import MetricsRegistry, default_metrics
from portalab.core.partitions import ensure_month_partitions
from portalab.core.time import Clock, utc_now
from portalab.modules.observability import event_types as _event_types  # noqa: F401 — registers event types
from portalab.modules.observability import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.observability import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.observability.alerts.service import AlertService
from portalab.modules.observability.collector.job import Collector
from portalab.modules.observability.components.adapters.core import register_core
from portalab.modules.observability.components.adapters.plugins import plugin_components
from portalab.modules.observability.components.adapters.services import service_components
from portalab.modules.observability.components.evaluator import Evaluation, HealthEvaluator, health_out
from portalab.modules.observability.detectors.runner import DetectorRunner
from portalab.modules.observability.errors.service import ErrorService
from portalab.modules.observability.escalation.service import EscalationService
from portalab.modules.observability.models import Anomaly
from portalab.modules.observability.observability import log
from portalab.modules.observability.overview.service import (
    ObservabilityRequiredActions,
    OverviewPanel,
    OverviewService,
)
from portalab.modules.observability.permissions import OBSERVABILITY_READ
from portalab.modules.observability.privacy import ObservabilityErasure
from portalab.modules.observability.retention import register_targets
from portalab.modules.observability.settings import ObservabilityConfig

OWNER = "module:observability"
COLLECT_JOB = "observability.collect"
ROLLUP_JOB = "observability.rollup"


class HealthCapability:
    def __init__(self, module: "ObservabilityModule") -> None:
        self.module = module

    async def component_health(self, component: str) -> dict[str, Any] | None:
        row = await self.module.evaluator.current(component)
        return health_out(row) if row else None

    async def problems(self, limit: int = 20) -> list[dict[str, Any]]:
        return await self.module.overview.problems(full_context=False, limit=limit)


class ObservabilityModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        *,
        config: ObservabilityConfig | None = None,
        clock: Clock | None = None,
        registry: ObservableRegistry = default_observables,
        metrics_registry: MetricsRegistry = default_metrics,
    ) -> None:
        self.config = config or ObservabilityConfig()
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self.registry = registry
        self.metrics_registry = metrics_registry
        self.collector = Collector(database, events, registry=metrics_registry, clock=clock)
        self.errors = ErrorService(database, self.collector.recorder, audit, clock=clock)
        self.evaluator = HealthEvaluator(database, events, registry, clock=clock)
        self.alerts = AlertService(database, events, capabilities, clock=clock)
        self.detectors = DetectorRunner(database, capabilities, lambda: self.config, clock=clock)
        self.escalation = EscalationService(
            database,
            events,
            audit,
            capabilities,
            lambda: self.config,
            clock=clock,
            on_anomaly=self._alert_anomaly,
        )
        self.overview = OverviewService(database, registry)

    def register_capabilities(self) -> None:
        config = lambda: self.config  # noqa: E731
        register_core(
            self.registry,
            database=self.database,
            capabilities=self.capabilities,
            config=config,
            metrics_registry=self.metrics_registry,
            collector=self.collector,
            clock=self.clock,
        )
        self.registry.declare_source(
            "services", service_components(self.capabilities, config, self.clock), owner=OWNER
        )
        self.registry.declare_source("plugins", plugin_components(self.capabilities), owner=OWNER)
        self.capabilities.provide(
            OBSERVABILITY_HEALTH, HealthCapability(self), instance_ref="observability", owner=OWNER
        )
        self.capabilities.provide(
            PANEL_CAPABILITY,
            OverviewPanel(self.overview),
            instance_ref="observability",
            owner=OWNER,
            metadata={"panel": "observability", "permission": OBSERVABILITY_READ, "order": 20},
        )
        self.capabilities.provide(
            REQUIRED_ACTION_CAPABILITY,
            ObservabilityRequiredActions(self.overview),
            instance_ref="observability",
            owner=OWNER,
        )
        self.capabilities.provide(
            ERASURE_CAPABILITY, ObservabilityErasure(self.database), instance_ref="observability", owner=OWNER
        )
        default_admin_surfaces.register(
            AdminSurface(
                "observability",
                "admin.surface.observability",
                "/admin/observability",
                OBSERVABILITY_READ,
                OWNER,
            )
        )
        register_targets(config)

    async def _alert_anomaly(self, anomaly: Anomaly) -> None:
        if anomaly.severity == "critical":
            await self.alerts.raise_alert(
                f"anomaly:{anomaly.fingerprint}",
                f"{anomaly.detector.replace('_', ' ')} on {anomaly.component}",
                "critical",
                anomaly.component,
                {"anomaly_id": str(anomaly.id)},
            )

    async def ensure_partitions(self) -> None:
        try:
            async with self.database.unit_of_work() as uow:
                await ensure_month_partitions(uow.session, "obs", "metric_samples", utc_now(self.clock))
        except Exception:
            log.warning("observability partition upkeep failed")

    async def cycle(self) -> list[Evaluation]:
        """One observation cycle: flush hooks, evaluate health, detect anomalies, escalate, alert."""
        await self.collector.flush()
        before = {row.component: (row.technical, row.functional) for row in await self.evaluator.all()}
        evaluations = await self.evaluator.evaluate_all()
        named = {c.name: c for c in await self.evaluator.registry.components()}
        for evaluation in evaluations:
            previous = before.get(evaluation.component)
            severe = evaluation.technical == "down" or evaluation.functional == "failing"
            was_severe = previous is not None and (previous[0] == "down" or previous[1] == "failing")
            if severe and not was_severe:
                # 027: alerts speak of « Radarr », not of « connector:01a1… »
                component = named.get(evaluation.component)
                label = (component.label if component else None) or evaluation.component
                await self.alerts.raise_alert(
                    f"component:{evaluation.component}",
                    f"{label} is {evaluation.status}",
                    "critical" if evaluation.component in ("portal", "db") else "warning",
                    evaluation.component,
                    {
                        "label": label,
                        "kind": component.kind if component else "component",
                        "status": evaluation.status,
                    },
                )
        await self.escalation.observe(await self.detectors.detect())
        await self.escalation.retry_pending()
        return evaluations

    def register_jobs(self, jobs: JobRegistry) -> list[Callable[[], Awaitable[None]]]:
        async def rollup() -> None:
            await self.ensure_partitions()
            await self.collector.rollup()

        return [
            register_periodic(
                jobs,
                self.database,
                COLLECT_JOB,
                timedelta(minutes=1),
                self.cycle,
                owner=OWNER,
                clock=self.clock,
            ),
            register_periodic(
                jobs, self.database, ROLLUP_JOB, timedelta(hours=1), rollup, owner=OWNER, clock=self.clock
            ),
            self.ensure_partitions,
        ]
