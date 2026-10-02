"""Shell integration fixtures: the shell module on the full platform with an isolated registry."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.events import ConsumerRegistry, EventTypeRegistry
from portalab.capabilities.navigation import NavigationRegistry
from portalab.capabilities.observability import ObservableRegistry
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.shell.module import ShellModule
from tests.integration.privacy.conftest import NOW
from tests.privacy_fixtures import FullPlatform, make_full_platform


@dataclass
class ShellHarness:
    full: FullPlatform
    module: ShellModule
    registry: NavigationRegistry
    consumers: ConsumerRegistry


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def sh(database: Database, tmp_path: Path, clock: FixedClock) -> ShellHarness:
    full = make_full_platform(database, tmp_path / "blobs", clock)
    await full.authz.catalog.sync()
    registry, consumers = NavigationRegistry(), ConsumerRegistry()
    module = ShellModule(
        database,
        full.authz.engine.events,
        full.authz.engine,
        full.identity.capabilities,
        registry=registry,
        clock=clock,
        event_types=EventTypeRegistry(),
        consumers=consumers,
        observables=ObservableRegistry(),
    )
    module.register()
    return ShellHarness(full, module, registry, consumers)


@pytest.fixture
def app(sh: ShellHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = sh.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        shell=sh.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http
