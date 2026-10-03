"""Media integration fixtures: the media module on the real event store with isolated registries, fake
providers registered per service (as 005 would after enabling a service) and an HTTP app."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.media import LIBRARY, PLAYBACK, REQUESTS
from portalab.capabilities.media.testkit import FakeLibrary, FakePlayback, FakeRequests
from portalab.capabilities.media_core import DetailBlockRegistry, MediaTypeRegistry
from portalab.capabilities.notifications import CategoryRegistry
from portalab.capabilities.observability import ObservableRegistry
from portalab.capabilities.record_sink import ServiceRef, SinkRegistry
from portalab.capabilities.search import SearchRegistry
from portalab.core.authz_port import Principal
from portalab.core.blobstore import FileSystemBlobStore
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.administration.config.service import Change
from portalab.modules.media.module import MediaModule
from tests.authz_fixtures import make_admin
from tests.events_fixtures import EventsHarness, make_events
from tests.integration.identity.helpers import create_user, module_of
from tests.integration.privacy.conftest import NOW


@dataclass
class MediaHarness:
    ev: EventsHarness
    module: MediaModule
    types: MediaTypeRegistry
    sinks: SinkRegistry
    widgets: WidgetRegistry
    search: SearchRegistry
    blocks: DetailBlockRegistry
    categories: CategoryRegistry

    @property
    def database(self) -> Database:
        return self.ev.full.database

    def service(self, n: int, connector: str = "fake") -> ServiceRef:
        service_id = UUID(int=n)
        return ServiceRef(service_id=service_id, source_system=f"{connector}:{service_id}")

    def provide(self, capability: str, service: ServiceRef, provider: Any) -> Any:
        self.ev.full.identity.capabilities.provide(
            capability, provider, instance_ref=str(service.service_id), owner=f"service:{service.service_id}"
        )
        return provider

    def library(self, service: ServiceRef) -> FakeLibrary:
        return self.provide(LIBRARY, service, FakeLibrary())  # type: ignore[no-any-return]

    def playback(self, service: ServiceRef) -> FakePlayback:
        return self.provide(PLAYBACK, service, FakePlayback())  # type: ignore[no-any-return]

    def requests(self, service: ServiceRef) -> FakeRequests:
        return self.provide(REQUESTS, service, FakeRequests())  # type: ignore[no-any-return]

    async def dispatch(self) -> None:
        for _ in range(10):
            runs = await self.ev.module.dispatcher.run_once()
            if not any(run.delivered for run in runs):
                return

    async def configure(self, key: str, value: Any) -> None:
        await self.ev.full.administration.config.apply(
            [Change(key, value)], Principal(channel="system"), admin_change=True
        )
        await self.module.refresh_config()

    async def events(self, prefix: str = "media.") -> list[tuple[str, dict[str, Any], str | None]]:
        from sqlalchemy import text

        async with self.database.session() as session:
            rows = await session.execute(
                text("SELECT type, payload, subject_id FROM events.events WHERE type LIKE :p ORDER BY seq"),
                {"p": f"{prefix}%"},
            )
            return [(r[0], dict(r[1]), r[2]) for r in rows]


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def media(database: Database, tmp_path: Path, clock: FixedClock) -> MediaHarness:
    ev = make_events(database, tmp_path / "blobs", clock)
    await ev.full.authz.catalog.sync()
    ev.module.register()
    types, sinks, widgets = MediaTypeRegistry(), SinkRegistry(), WidgetRegistry()
    search, blocks, categories = SearchRegistry(), DetailBlockRegistry(), CategoryRegistry()
    module = MediaModule(
        database,
        ev.publisher,
        ev.full.authz.audit,
        ev.full.identity.capabilities,
        ev.full.authz.engine,
        blobs=FileSystemBlobStore(tmp_path / "media-blobs"),
        visibility=ev.full.privacy.filter,
        clock=clock,
        event_types=ev.types,
        consumers=ev.consumers,
        sinks=sinks,
        types=types,
        blocks=blocks,
        widgets=widgets,
        search=search,
        categories=categories,
        observables=ObservableRegistry(),
    )
    module.register()
    return MediaHarness(ev, module, types, sinks, widgets, search, blocks, categories)


@pytest.fixture
def app(media: MediaHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = media.ev.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        media=media.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http


async def users(app: FastAPI, media: MediaHarness, *names: str, admin: str | None = None) -> dict[str, UUID]:
    out = {name: await create_user(module_of(app), name) for name in (*names, *([admin] if admin else []))}
    if admin:
        await make_admin(media.ev.full, out[admin])
    return out
