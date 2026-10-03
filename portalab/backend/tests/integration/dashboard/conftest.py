"""Dashboard integration fixtures: the dashboard module on the full platform with isolated registries,
fake health/service directories, and helpers."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.events import ConsumerRegistry, EventTypeRegistry
from portalab.capabilities.health import SERVICE_DIRECTORY, SERVICE_STATE, ServiceInfo, ServiceStateView
from portalab.capabilities.observability import ObservableRegistry
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.dashboard.module import DashboardModule
from tests.integration.privacy.conftest import NOW
from tests.privacy_fixtures import FullPlatform, make_full_platform


class FakeHealth:
    def __init__(self) -> None:
        self.down = False
        self.views = [
            ServiceStateView("s1", "operational", NOW - timedelta(days=3), NOW, 1.0, NOW),
            ServiceStateView("s2", "unavailable", NOW - timedelta(hours=1), NOW, 0.5, NOW),
        ]

    async def all(self) -> list[ServiceStateView]:
        if self.down:
            raise RuntimeError("health down")
        return list(self.views)

    async def get(self, service_id: str) -> ServiceStateView | None:
        return next((v for v in self.views if v.service_id == service_id), None)


class FakeDirectory:
    async def services(self) -> list[ServiceInfo]:
        return [
            ServiceInfo(id="s1", name="Media", connector="jellyfin", state="enabled"),
            ServiceInfo(id="s2", name="Books", connector="kavita", state="enabled"),
        ]

    async def service(self, service_id: str) -> ServiceInfo | None:
        return None


@dataclass
class DashboardHarness:
    full: FullPlatform
    module: DashboardModule
    registry: WidgetRegistry
    consumers: ConsumerRegistry
    health: FakeHealth = field(default_factory=FakeHealth)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def dash(database: Database, tmp_path: Path, clock: FixedClock) -> DashboardHarness:
    full = make_full_platform(database, tmp_path / "blobs", clock)
    await full.authz.catalog.sync()
    registry = WidgetRegistry()
    consumers = ConsumerRegistry()
    capabilities = full.identity.capabilities
    module = DashboardModule(
        database,
        full.authz.engine.events,
        full.authz.audit,
        capabilities,
        full.authz.engine,
        clock=clock,
        registry=registry,
        event_types=EventTypeRegistry(),
        consumers=consumers,
        observables=ObservableRegistry(),
    )
    module.register()
    for key, validator in module.validators.table().items():
        full.administration.registry.register_validator(key, validator, owner="module:dashboard")
    harness = DashboardHarness(full, module, registry, consumers)
    capabilities.provide(SERVICE_STATE, harness.health, instance_ref="t", owner="module:health")
    capabilities.provide(SERVICE_DIRECTORY, FakeDirectory(), instance_ref="t", owner="module:connectors")
    return harness


@pytest.fixture
def app(dash: DashboardHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = dash.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        dashboard=dash.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http
