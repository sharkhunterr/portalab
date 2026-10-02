"""Privacy module facade: visibility engine and filter, policies, retention, purge, privacy center,
aggregation guard; kernel retention targets and the privacy permissions are declared on import."""

from datetime import timedelta
from typing import Any

from portalab.capabilities.administration import AdminSurface, default_admin_surfaces
from portalab.capabilities.aggregation import CAPABILITY as AGGREGATION_GUARD
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditSink
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.time import Clock
from portalab.modules.privacy import event_types as _event_types  # noqa: F401 — registers event types
from portalab.modules.privacy import permissions  # noqa: F401 — declares privacy permissions
from portalab.modules.privacy.aggregation.guard import AggregationGuard
from portalab.modules.privacy.center.service import PrivacyCenter
from portalab.modules.privacy.policies.service import PolicyService
from portalab.modules.privacy.purge.service import JOB as PURGE_JOB
from portalab.modules.privacy.purge.service import ServicePurge
from portalab.modules.privacy.retention import registry as _targets  # noqa: F401 — kernel targets
from portalab.modules.privacy.retention.engine import RetentionEngine
from portalab.modules.privacy.settings import PrivacyConfig
from portalab.modules.privacy.visibility.filter import PrivacyVisibilityFilter
from portalab.modules.privacy.visibility.providers import PreferenceProviders
from portalab.modules.privacy.visibility.service import VisibilityService

OWNER = "module:privacy"
RETENTION_JOB = "privacy.retention_run"


class PrivacyModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        *,
        config: PrivacyConfig | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.config = config or PrivacyConfig()
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self.providers = PreferenceProviders(capabilities)
        self.visibility = VisibilityService(database, self.providers, config=self.config, clock=clock)
        self.filter = PrivacyVisibilityFilter(self.visibility)
        self.policies = PolicyService(database, audit, events, clock=clock)
        self.retention = RetentionEngine(database, events, config=self.config, clock=clock)
        self.purge = ServicePurge(database, capabilities, audit, events, clock=clock)
        self.center = PrivacyCenter(self.visibility, self.providers, config=self.config)
        self.guard = AggregationGuard(self.config.min_aggregate_size)

    def register_capabilities(self) -> None:
        self.capabilities.provide(AGGREGATION_GUARD, self.guard, instance_ref="privacy", owner=OWNER)
        default_admin_surfaces.register(
            AdminSurface("privacy", "admin.surface.privacy", "/admin/privacy", "privacy.manage", OWNER)
        )

    def register_jobs(self, registry: JobRegistry) -> list[Any]:
        async def purge(payload: dict[str, Any]) -> None:
            await self.purge.run(str(payload["service_id"]))

        registry.register(
            PURGE_JOB, purge, idempotency="purging already-purged data removes nothing", owner=OWNER
        )
        seed = register_periodic(
            registry,
            self.database,
            RETENTION_JOB,
            timedelta(days=1),
            self.retention.run,
            owner=OWNER,
            clock=self.clock,
        )
        return [seed]
