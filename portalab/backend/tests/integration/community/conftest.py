"""Community integration fixtures: the module on the real event store and the real 021 visibility filter,
isolated registries, a fake 013 progression reader (that can be taken down) with its own ``progression``
preference, a fixed clock and real users."""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from portalab.capabilities.community import SectionRegistry, ShelfRegistry
from portalab.capabilities.content import CalendarSourceRegistry
from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.economy import Progress
from portalab.capabilities.events import EventType
from portalab.capabilities.observability import ObservableRegistry
from portalab.capabilities.search import SearchRegistry
from portalab.capabilities.statistics import PROGRESSION
from portalab.capabilities.visibility import PREFERENCE_CAPABILITY, Level
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.community.module import CommunityModule
from portalab.modules.gamification.events import register_event_types as gamification_types
from tests.events_fixtures import EventsHarness, make_events
from tests.integration.privacy.conftest import NOW


class Secret(BaseModel):
    value: int = 0


@dataclass
class FakeProgression:
    """The 013 ``ProgressionReader`` as Community sees it; ``down`` makes every call fail."""

    down: bool = False

    async def level(self, user_id: UUID) -> int:
        return (await self.progress(user_id)).level

    async def has_achievement(self, user_id: UUID, achievement: str) -> bool:
        return achievement == "first-steps"

    async def progress(self, user_id: UUID) -> Progress:
        if self.down:
            raise RuntimeError("013 is down")
        return Progress(user_id, 120, 3, 100, 200, 7, 5, 0, 1)

    async def achievement_list(self, user_id: UUID, limit: int = 50) -> list[dict[str, str]]:
        if self.down:
            raise RuntimeError("013 is down")
        return [{"key": "first-steps", "label": "First steps", "unlocked_at": NOW.isoformat()}]


@dataclass
class ProgressionPreferences:
    levels: dict[UUID, Level] = field(default_factory=dict)

    async def get_preference(self, subject: UUID, datum_class: str, datum_ref: str | None) -> Level | None:
        return self.levels.get(subject) if datum_class == "progression" else None

    async def set_preference(
        self, subject: UUID, datum_class: str, datum_ref: str | None, level: Level
    ) -> None:
        self.levels[subject] = level


@dataclass
class CoHarness:
    ev: EventsHarness
    module: CommunityModule
    clock: FixedClock
    progression: FakeProgression
    progression_preferences: ProgressionPreferences
    people: dict[str, UUID] = field(default_factory=dict)

    @property
    def database(self) -> Database:
        return self.ev.full.database

    def p(self, name: str) -> Principal:
        return Principal(user_id=self.people[name])

    async def prefer(self, name: str, datum: str, level: Level) -> None:
        if datum == "progression":
            await self.progression_preferences.set_preference(self.people[name], datum, None, level)
        else:
            provider = next(
                p.provider
                for p in self.module.capabilities.system_providers(PREFERENCE_CAPABILITY)
                if p.instance_ref == "community"
            )
            await provider.set_preference(self.people[name], datum, None, level)

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: Mapping[str, Any] | None = None,
        *,
        dedup: str | None = None,
    ) -> None:
        async with self.database.unit_of_work() as uow:
            await self.ev.publisher.publish(
                uow.session,
                event_type,
                dict(payload or {}),
                occurred_at=self.clock.now(),
                actor=Principal(user_id=self.people[actor], channel="system"),
                source="test",
                dedup_key=dedup,
            )
        await self.dispatch()

    async def dispatch(self) -> None:
        for _ in range(20):
            runs = await self.ev.module.dispatcher.run_once()
            if not any(run.delivered for run in runs):
                return


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def harness(database: Database, tmp_path: Path, clock: FixedClock) -> CoHarness:
    ev = make_events(database, tmp_path / "blobs", clock)
    await ev.full.authz.catalog.sync()
    ev.module.register()
    gamification_types(ev.types)
    ev.types.register(EventType("test.secret", "test:domain", schema=Secret, open_payload=False))
    capabilities = ev.full.identity.capabilities
    progression, preferences = FakeProgression(), ProgressionPreferences()
    capabilities.provide(PROGRESSION, progression, instance_ref="fake013", owner="module:test")
    capabilities.provide(
        PREFERENCE_CAPABILITY,
        preferences,
        instance_ref="fake013",
        owner="module:test",
        metadata={"datum_classes": ["progression"]},
    )
    module = CommunityModule(
        database,
        ev.publisher,
        ev.full.authz.audit,
        capabilities,
        ev.full.authz.engine,
        clock=clock,
        visibility=ev.full.privacy.filter,
        event_types=ev.types,
        consumers=ev.consumers,
        sections=SectionRegistry(),
        shelves=ShelfRegistry(),
        widgets=WidgetRegistry(),
        search=SearchRegistry(),
        calendar_sources=CalendarSourceRegistry(),
        observables=ObservableRegistry(),
    )
    module.register()
    module.config = type(module.config)(feed_event_types=[*module.config.feed_event_types, "test.secret"])
    return CoHarness(ev, module, clock, progression, preferences)


@pytest.fixture
def app(harness: CoHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = harness.ev.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        community=harness.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http


@pytest.fixture
async def co(harness: CoHarness, app: FastAPI) -> CoHarness:
    """``boss`` (admin), ``mona`` (moderator), ``ursula``, ``ulrich`` and ``vera`` (users)."""
    from tests.authz_fixtures import make_admin
    from tests.integration.identity.helpers import create_user, module_of

    identity = module_of(app)
    harness.people = {
        name: await create_user(identity, name, display_name=name.capitalize())
        for name in ("boss", "mona", "ursula", "ulrich", "vera")
    }
    await make_admin(harness.ev.full, harness.people["boss"])
    admin = Principal(user_id=harness.people["boss"])
    await harness.ev.full.authz.grants.assign_role(admin, harness.people["mona"], "moderator")
    return harness


def with_marketplace(co: CoHarness) -> Any:
    """Adds the real 015 lifecycle (``marketplace.project_lifecycle``) to the community harness."""
    from portalab.capabilities.ai import AIToolRegistry
    from portalab.capabilities.marketplace import ProductTypeRegistry
    from portalab.capabilities.observability import ObservableRegistry as Observables
    from portalab.modules.marketplace.module import MarketplaceModule

    module = MarketplaceModule(
        co.database,
        co.ev.publisher,
        co.ev.full.authz.audit,
        co.module.capabilities,
        co.ev.full.authz.engine,
        clock=co.clock,
        event_types=co.ev.types,
        observables=Observables(),
        product_types=ProductTypeRegistry(),
        widgets=WidgetRegistry(),
        search=SearchRegistry(),
        tools=AIToolRegistry(),
        sections=SectionRegistry(),
    )
    module.register()
    return module
