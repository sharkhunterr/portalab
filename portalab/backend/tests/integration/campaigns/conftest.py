"""Campaign integration fixtures: Campaigns and Gamification on the real event store, a fake media attribute
provider, a fixed clock and real users (created through the app's identity module)."""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from portalab.capabilities.activity import CAPABILITY as ACTIVITY
from portalab.capabilities.activity import ActivityAttributes
from portalab.capabilities.ai import AIToolRegistry
from portalab.capabilities.automation_actions import ActionRegistry
from portalab.capabilities.content import CalendarSourceRegistry
from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.events import EventType
from portalab.capabilities.observability import ObservableRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.campaigns.module import CampaignsModule
from portalab.modules.gamification.module import GamificationModule
from tests.events_fixtures import EventsHarness, make_events
from tests.integration.privacy.conftest import NOW

SYSTEM = Principal(channel="system")


class Played(BaseModel):
    media_id: str
    minutes: int = 30


class FakeMedia:
    """``activity.attributes`` for ``media.played``: the catalog of the test (``None`` = unavailable)."""

    def __init__(self) -> None:
        self.catalog: dict[str, ActivityAttributes] | None = {
            "m1": ActivityAttributes("movie", ("Horror",), "Halloween Night", "Halloween Night"),
            "m2": ActivityAttributes("movie", ("comedy",), "Holiday Fun"),
            "m3": ActivityAttributes("series", ("horror",), "Haunted Hôtel", "Hotel Hanté"),
        }
        self.calls = 0

    def handles(self, event_type: str) -> bool:
        return event_type == "media.played"

    async def attributes(self, event_type: str, payload: dict[str, Any]) -> ActivityAttributes | None:
        self.calls += 1
        if self.catalog is None:
            raise RuntimeError("media down")
        return self.catalog.get(str(payload.get("media_id")))


HALLOWEEN: dict[str, Any] = {
    "names": {"en": "Halloween", "fr": "Halloween"},
    "timezone": "Europe/Paris",
    "schedule": {
        "start_at": "2026-10-20T00:00:00",
        "end_at": "2026-11-01T00:00:00",
        "recurrence": {"kind": "yearly", "count": 2},
    },
    "modifiers": [
        {
            "id": "horror_xp",
            "value": "xp",
            "factor": 2,
            "when": {"media_kind": ["movie"], "genre": ["horror"]},
        },
        {
            "id": "horror_coins",
            "value": "coins",
            "factor": 1.5,
            "when": {"media_kind": ["movie"], "genre": ["horror"]},
        },
        {"id": "title_xp", "value": "xp", "factor": 2, "when": {"title_contains": ["halloween"]}},
    ],
}


@dataclass
class CampHarness:
    ev: EventsHarness
    campaigns: CampaignsModule
    gamification: GamificationModule
    clock: FixedClock
    media: FakeMedia
    widgets: WidgetRegistry
    calendar: CalendarSourceRegistry
    people: dict[str, UUID] = field(default_factory=dict)

    @property
    def database(self) -> Database:
        return self.ev.full.database

    def p(self, name: str) -> Principal:
        return Principal(user_id=self.people[name])

    async def create(self, key: str = "halloween", definition: Mapping[str, Any] | None = None) -> UUID:
        campaign = await self.campaigns.definitions.create(self.p("boss"), key, definition or HALLOWEEN)
        await self.campaigns.reconciler.run()
        return campaign.id

    async def at(self, moment: datetime) -> None:
        """Moves the clock and reconciles the schedule."""
        self.clock.set(moment)
        await self.campaigns.reconciler.run()

    async def play(self, user: UUID, media_id: str, at: datetime, minutes: int = 30) -> None:
        async with self.database.unit_of_work() as uow:
            await self.ev.publisher.publish(
                uow.session,
                "media.played",
                {"media_id": media_id, "minutes": minutes},
                occurred_at=at,
                actor=Principal(user_id=user),
                source="test",
            )
        for _ in range(10):
            runs = await self.ev.module.dispatcher.run_once()
            if not any(run.delivered for run in runs):
                break


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def harness(database: Database, tmp_path: Path, clock: FixedClock) -> CampHarness:
    ev = make_events(database, tmp_path / "blobs", clock)
    await ev.full.authz.catalog.sync()
    ev.module.register()
    ev.types.register(
        EventType(
            "media.played", "test:media", schema=Played, open_payload=False, rewardable=frozenset({"minutes"})
        )
    )
    capabilities = ev.full.identity.capabilities
    media = FakeMedia()
    capabilities.provide(ACTIVITY, media, instance_ref="test-media", owner="module:media")
    widgets, calendar = WidgetRegistry(), CalendarSourceRegistry()
    gamification = GamificationModule(
        database,
        ev.publisher,
        ev.full.authz.audit,
        capabilities,
        ev.full.authz.engine,
        clock=clock,
        visibility=ev.full.privacy.filter,
        event_types=ev.types,
        consumers=ev.consumers,
        widgets=WidgetRegistry(),
        observables=ObservableRegistry(),
        actions=ActionRegistry(),
        tools=AIToolRegistry(),
    )
    gamification.register()
    await gamification.levels.ensure_default()
    campaigns = CampaignsModule(
        database,
        ev.publisher,
        ev.full.authz.audit,
        capabilities,
        ev.full.authz.engine,
        clock=clock,
        event_types=ev.types,
        widgets=widgets,
        observables=ObservableRegistry(),
        calendar_sources=calendar,
    )
    campaigns.register()
    return CampHarness(ev, campaigns, gamification, clock, media, widgets, calendar)


@pytest.fixture
def app(harness: CampHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = harness.ev.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        gamification=harness.gamification,
        campaigns=harness.campaigns,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http


@pytest.fixture
async def cm(harness: CampHarness, app: FastAPI) -> CampHarness:
    """The harness with users ``boss`` (admin), ``ursula`` and ``ulrich``."""
    from tests.authz_fixtures import make_admin
    from tests.integration.identity.helpers import create_user, module_of

    harness.people = {name: await create_user(module_of(app), name) for name in ("boss", "ursula", "ulrich")}
    await make_admin(harness.ev.full, harness.people["boss"])
    return harness


def paris(month: int, day: int, hour: int = 12, year: int = 2026) -> datetime:
    from zoneinfo import ZoneInfo

    return datetime(year, month, day, hour, tzinfo=ZoneInfo("Europe/Paris"))


def later(moment: datetime, **delta: float) -> datetime:
    return moment + timedelta(**delta)
