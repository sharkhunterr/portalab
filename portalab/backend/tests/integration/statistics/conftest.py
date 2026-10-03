"""Statistics integration fixtures: the statistics module on the real event store (007 publisher,
dispatcher and replay) with isolated registries and seeded test event types."""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.events import EventType
from portalab.capabilities.observability import ObservableRegistry
from portalab.capabilities.service_events import STATUS_CHANGED_TYPE
from portalab.capabilities.statistics import PackRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.statistics.module import StatisticsModule
from tests.events_fixtures import EventsHarness, make_events
from tests.integration.privacy.conftest import NOW

SALT = b"test-only-statistics-salt"


class Played(BaseModel):
    minutes: int
    genre: str
    service_id: str


@dataclass
class StatsHarness:
    ev: EventsHarness
    module: StatisticsModule
    packs: PackRegistry
    widgets: WidgetRegistry

    @property
    def database(self) -> Database:
        return self.ev.full.database

    async def publish(
        self, event_type: str, payload: Mapping[str, Any], *, at: datetime, actor: UUID | None = None
    ) -> None:
        async with self.database.unit_of_work() as uow:
            await self.ev.publisher.publish(
                uow.session,
                event_type,
                dict(payload),
                occurred_at=at,
                actor=Principal(user_id=actor) if actor else None,
                source="test",
            )

    async def dispatch(self) -> None:
        for _ in range(10):
            runs = await self.ev.module.dispatcher.run_once()
            if not any(run.delivered for run in runs):
                return

    async def define(self, definition: Mapping[str, Any]) -> int:
        version = await self.module.definitions.save(None, definition)
        await self.module.activate(Principal(channel="system"), definition["key"], version)
        return version


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def stats(database: Database, tmp_path: Path, clock: FixedClock) -> StatsHarness:
    ev = make_events(database, tmp_path / "blobs", clock)
    await ev.full.authz.catalog.sync()
    ev.module.register()
    ev.types.register(
        EventType(
            "media.played",
            "test:media",
            schema=Played,
            open_payload=False,
            aggregatable=frozenset({"minutes", "genre", "service_id"}),
        )
    )
    ev.types.register(EventType("user.signed_in", "module:identity", retention_class="technical"))
    ev.types.register(STATUS_CHANGED_TYPE)
    packs, widgets = PackRegistry(), WidgetRegistry()
    module = StatisticsModule(
        database,
        ev.publisher,
        ev.full.authz.audit,
        ev.full.identity.capabilities,
        ev.full.authz.engine,
        salt=SALT,
        visibility=ev.full.privacy.filter,
        clock=clock,
        event_types=ev.types,
        consumers=ev.consumers,
        packs=packs,
        widgets=widgets,
        observables=ObservableRegistry(),
    )
    module.register()
    return StatsHarness(ev, module, packs, widgets)


@pytest.fixture
def app(stats: StatsHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = stats.ev.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        statistics=stats.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http
