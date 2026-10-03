"""Support integration fixtures: the support module on the full platform with isolated registries and a
fake service directory."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.events import EventTypeRegistry
from portalab.capabilities.health import SERVICE_DIRECTORY, ServiceInfo
from portalab.capabilities.observability import ObservableRegistry
from portalab.capabilities.search import SearchRegistry
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.support.module import SupportModule
from tests.integration.privacy.conftest import NOW
from tests.privacy_fixtures import FullPlatform, make_full_platform


class FakeDirectory:
    async def services(self) -> list[ServiceInfo]:
        return [
            ServiceInfo(id="s1", name="Media", connector="jellyfin", state="enabled"),
            ServiceInfo(id="s2", name="Books", connector="kavita", state="enabled"),
        ]

    async def service(self, service_id: str) -> ServiceInfo | None:
        return None


@dataclass
class SupportHarness:
    full: FullPlatform
    module: SupportModule
    widgets: WidgetRegistry
    search: SearchRegistry


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def support(database: Database, tmp_path: Path, clock: FixedClock) -> SupportHarness:
    full = make_full_platform(database, tmp_path / "blobs", clock)
    await full.authz.catalog.sync()
    widgets, search = WidgetRegistry(), SearchRegistry()
    capabilities = full.identity.capabilities
    module = SupportModule(
        database,
        full.authz.engine.events,
        full.authz.audit,
        capabilities,
        full.authz.engine,
        clock=clock,
        widgets=widgets,
        search=search,
        event_types=EventTypeRegistry(),
        observables=ObservableRegistry(),
    )
    module.register()
    capabilities.provide(SERVICE_DIRECTORY, FakeDirectory(), instance_ref="t", owner="module:connectors")
    return SupportHarness(full, module, widgets, search)


@pytest.fixture
def app(support: SupportHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = support.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        support=support.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http
