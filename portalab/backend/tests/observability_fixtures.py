"""Spec 025 fixtures: Observability on top of the Health harness, with isolated hook queue and component
registry so tests never see each other's observations."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import text

from portalab.capabilities.events import ConsumerRegistry
from portalab.capabilities.observability import ObservableRegistry
from portalab.core.db import Database
from portalab.core.metrics import MetricsRegistry
from portalab.core.time import Clock
from portalab.modules.events.module import EventsModule
from portalab.modules.observability.module import ObservabilityModule
from portalab.modules.observability.settings import ObservabilityConfig
from tests.health_fixtures import HealthHarness, make_health


@dataclass
class ObsHarness:
    hl: HealthHarness
    module: ObservabilityModule
    hooks: MetricsRegistry
    registry: ObservableRegistry
    events: EventsModule
    sent_alerts: list[Any] = field(default_factory=list)

    @property
    def database(self) -> Database:
        return self.module.database

    async def outbox(self, prefix: str) -> list[dict[str, Any]]:
        return await self.hl.outbox(prefix)

    async def count(self, table: str) -> int:
        async with self.database.session() as session:
            return int(await session.scalar(text(f"SELECT count(*) FROM obs.{table}")) or 0)


async def make_observability(
    database: Database,
    blob_root: Path,
    clock: Clock | None = None,
    *,
    config: ObservabilityConfig | None = None,
) -> ObsHarness:
    hl = await make_health(database, blob_root, clock)
    capabilities = hl.cn.full.identity.capabilities
    # isolated consumers: modules wired by other tests (e.g. a ``*`` subscriber) must not join this one
    events = EventsModule(
        database, hl.cn.full.authz.audit, capabilities, clock=clock, consumers=ConsumerRegistry()
    )
    events.register()
    hooks, registry = MetricsRegistry(), ObservableRegistry()
    module = ObservabilityModule(
        database,
        hl.cn.full.authz.engine.events,
        hl.cn.full.authz.audit,
        capabilities,
        config=config or ObservabilityConfig(),
        clock=clock,
        registry=registry,
        metrics_registry=hooks,
    )
    module.register_capabilities()
    return ObsHarness(hl, module, hooks, registry, events)
