"""Gamification integration fixtures: the module on the real event store (007 publisher and dispatcher) with
isolated registries, a rewardable test event type, real users and helpers to publish rules and events."""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from portalab.capabilities.ai import AIToolRegistry
from portalab.capabilities.automation_actions import ActionRegistry
from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.events import Envelope, EventType
from portalab.capabilities.observability import ObservableRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.gamification.module import GamificationModule
from tests.events_fixtures import EventsHarness, make_events
from tests.integration.privacy.conftest import NOW

SYSTEM = Principal(channel="system")


class Played(BaseModel):
    minutes: int
    genre: str


@dataclass
class GamHarness:
    ev: EventsHarness
    module: GamificationModule
    clock: FixedClock
    actions: ActionRegistry
    tools: AIToolRegistry
    widgets: WidgetRegistry
    people: dict[str, UUID] = field(default_factory=dict)

    @property
    def database(self) -> Database:
        return self.ev.full.database

    def p(self, name: str) -> Principal:
        return Principal(user_id=self.people[name])

    async def rule(self, key: str, definition: Mapping[str, Any]) -> int:
        row = await self.module.rules.save(SYSTEM, key, definition)
        await self.module.rules.publish(SYSTEM, key, row.version)
        return row.version

    async def emit(
        self,
        user: UUID,
        payload: Mapping[str, Any] | None = None,
        *,
        at: datetime | None = None,
        event_type: str = "media.played",
    ) -> None:
        async with self.database.unit_of_work() as uow:
            await self.ev.publisher.publish(
                uow.session,
                event_type,
                dict(payload or {"minutes": 30, "genre": "rock"}),
                occurred_at=at or self.clock.now() + timedelta(seconds=1),
                actor=Principal(user_id=user),
                source="test",
            )
        await self.dispatch()

    async def dispatch(self) -> None:
        for _ in range(10):
            runs = await self.ev.module.dispatcher.run_once()
            if not any(run.delivered for run in runs):
                return

    def envelope(
        self,
        user: UUID,
        payload: Mapping[str, Any] | None = None,
        *,
        at: datetime | None = None,
        event_type: str = "media.played",
    ) -> Envelope:
        at = at or self.clock.now() + timedelta(seconds=1)
        return Envelope(
            event_id=uuid4(),
            seq=0,
            type=event_type,
            type_version=1,
            occurred_at=at,
            received_at=at,
            source_system="test",
            source_event_id=None,
            actor_user_id=user,
            actor_kind="user",
            subject_type=None,
            subject_id=None,
            payload=dict(payload or {"minutes": 30, "genre": "rock"}),
            provenance={},
            correlation_id=None,
        )

    async def balance(self, user: UUID, value: str = "xp") -> int:
        return await self.module.economy.balance(user, value)  # type: ignore[arg-type]


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def harness(database: Database, tmp_path: Path, clock: FixedClock) -> GamHarness:
    ev = make_events(database, tmp_path / "blobs", clock)
    await ev.full.authz.catalog.sync()
    ev.module.register()
    ev.types.register(
        EventType(
            "media.played",
            "test:media",
            schema=Played,
            open_payload=False,
            rewardable=frozenset({"minutes", "genre"}),
        )
    )
    ev.types.register(EventType("wiki.page_published", "test:wiki"))
    actions, tools, widgets = ActionRegistry(), AIToolRegistry(), WidgetRegistry()
    module = GamificationModule(
        database,
        ev.publisher,
        ev.full.authz.audit,
        ev.full.identity.capabilities,
        ev.full.authz.engine,
        clock=clock,
        visibility=ev.full.privacy.filter,
        event_types=ev.types,
        consumers=ev.consumers,
        widgets=widgets,
        observables=ObservableRegistry(),
        actions=actions,
        tools=tools,
    )
    module.register()
    await module.levels.ensure_default()
    return GamHarness(ev, module, clock, actions, tools, widgets)


@pytest.fixture
def app(harness: GamHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = harness.ev.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        gamification=harness.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http


@pytest.fixture
async def gm(harness: GamHarness, app: FastAPI) -> GamHarness:
    """The harness with real users: ``boss`` (admin), ``ursula`` and ``ulrich``."""
    from tests.authz_fixtures import make_admin
    from tests.integration.identity.helpers import create_user, module_of

    harness.people = {name: await create_user(module_of(app), name) for name in ("boss", "ursula", "ulrich")}
    await make_admin(harness.ev.full, harness.people["boss"])
    return harness


RULE = {
    "event_type": "media.played",
    "grants": [{"value": "xp", "amount": 20}, {"value": "coins", "amount": 5}],
}
