"""i18n integration fixtures: the i18n module on the full platform (Administration config + ports)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.events import ConsumerRegistry, EventTypeRegistry
from portalab.capabilities.observability import ObservableRegistry
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.i18n.catalog.plugins import PluginCatalogs
from portalab.modules.i18n.content.localizer import ContentKinds
from portalab.modules.i18n.module import I18nModule
from tests.integration.privacy.conftest import NOW
from tests.privacy_fixtures import FullPlatform, make_full_platform


@dataclass
class I18nHarness:
    full: FullPlatform
    module: I18nModule
    consumers: ConsumerRegistry


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def i18n(database: Database, tmp_path: Path, clock: FixedClock) -> I18nHarness:
    full = make_full_platform(database, tmp_path / "blobs", clock)
    await full.authz.catalog.sync()
    consumers = ConsumerRegistry()
    module = I18nModule(
        database,
        full.authz.engine.events,
        full.authz.audit,
        full.identity.capabilities,
        clock=clock,
        plugins=PluginCatalogs(),
        content_kinds=ContentKinds(),
        event_types=EventTypeRegistry(),
        consumers=consumers,
        observables=ObservableRegistry(),
    )
    module.register()
    for key, validator in module.validators.table().items():
        full.administration.registry.register_validator(key, validator, owner="module:i18n")
    return I18nHarness(full, module, consumers)


@pytest.fixture
def app(i18n: I18nHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = i18n.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        i18n=i18n.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http
