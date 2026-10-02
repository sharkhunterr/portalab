"""Search integration fixtures: the search module on the full platform with isolated registries, the
users provider from identity, a fake service directory and an optional fake assistant."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.events import EventTypeRegistry
from portalab.capabilities.health import SERVICE_DIRECTORY, ServiceInfo
from portalab.capabilities.navigation import NavigationContribution, NavigationRegistry
from portalab.capabilities.observability import ObservableRegistry
from portalab.capabilities.search import SearchRegistry
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.identity.search_provider import UsersSearchProvider
from portalab.modules.search.module import SearchModule
from tests.integration.privacy.conftest import NOW
from tests.privacy_fixtures import FullPlatform, make_full_platform


class FakeDirectory:
    def __init__(self) -> None:
        self.items = [
            ServiceInfo(id="s1", name="Jellyfin Media", connector="jellyfin", state="enabled"),
            ServiceInfo(id="s2", name="Café Books", connector="kavita", state="error"),
        ]

    async def services(self) -> list[ServiceInfo]:
        return list(self.items)

    async def service(self, service_id: str) -> ServiceInfo | None:
        return next((s for s in self.items if s.id == service_id), None)


@dataclass
class SearchHarness:
    full: FullPlatform
    module: SearchModule
    registry: SearchRegistry
    navigation: NavigationRegistry
    directory: FakeDirectory = field(default_factory=FakeDirectory)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def search(database: Database, tmp_path: Path, clock: FixedClock) -> SearchHarness:
    full = make_full_platform(database, tmp_path / "blobs", clock)
    await full.authz.catalog.sync()
    registry = SearchRegistry()
    navigation = NavigationRegistry()
    navigation.register(
        NavigationContribution(
            key="health.services",
            owner="module:health",
            kind="entry",
            label_key="nav.services",
            route="/services",
            required_permission="services.read",
            keywords=("status",),
        )
    )
    navigation.register(
        NavigationContribution(
            key="audit.log",
            owner="module:audit",
            kind="entry",
            label_key="nav.admin.audit",
            route="/admin/audit",
            required_permission="audit.read",
        )
    )
    capabilities = full.identity.capabilities
    module = SearchModule(
        database,
        full.authz.engine.events,
        full.authz.audit,
        capabilities,
        full.authz.engine,
        clock=clock,
        registry=registry,
        navigation=navigation,
        event_types=EventTypeRegistry(),
        observables=ObservableRegistry(),
    )
    module.register()
    registry.register(UsersSearchProvider(full.identity), owner="module:identity")
    harness = SearchHarness(full, module, registry, navigation)
    capabilities.provide(SERVICE_DIRECTORY, harness.directory, instance_ref="test", owner="module:connectors")
    return harness


@pytest.fixture
def app(search: SearchHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = search.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        search=search.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http
