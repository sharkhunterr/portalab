"""Marketplace integration fixtures: the module on the real event store with the real 013 economy (ledger
reservations), isolated registries, a fixed clock and real users."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.ai import AIToolRegistry
from portalab.capabilities.automation_actions import ActionRegistry
from portalab.capabilities.community import SectionRegistry
from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.marketplace import ProductTypeRegistry
from portalab.capabilities.observability import ObservableRegistry
from portalab.capabilities.search import SearchRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.gamification.ledger.writer import Entry
from portalab.modules.gamification.module import GamificationModule
from portalab.modules.marketplace.module import MarketplaceModule
from tests.events_fixtures import EventsHarness, make_events
from tests.integration.privacy.conftest import NOW

RULES = {"consume_at": "released", "min_funding": 5, "max_funding_per_user": 200}


@dataclass
class MkHarness:
    ev: EventsHarness
    module: MarketplaceModule
    economy: GamificationModule
    clock: FixedClock
    people: dict[str, UUID] = field(default_factory=dict)

    @property
    def database(self) -> Database:
        return self.ev.full.database

    def p(self, name: str) -> Principal:
        return Principal(user_id=self.people[name])

    async def coins(self, name: str, amount: int) -> None:
        async with self.database.unit_of_work() as uow:
            await self.economy.writer.record(
                uow.session,
                Entry(
                    user_id=self.people[name],
                    value="coins",
                    delta=amount,
                    kind="grant",
                    source_kind="system",
                    idempotency_key=f"seed:{name}:{amount}:{self.clock.now().isoformat()}",
                    occurred_at=self.clock.now(),
                ),
            )

    async def balance(self, name: str) -> int:
        return await self.economy.economy.balance(self.people[name], "coins")

    async def project(self, title: str = "Dark mode", *, open_with: dict[str, Any] | None = None) -> UUID:
        ref = await self.module.projects.register(f"proposal-{title}", self.people.get("ursula"), title)
        if open_with is not None:
            await self.module.transition(self.p("boss"), ref.id, "proposal")
            await self.module.transition(self.p("boss"), ref.id, "open", rules=open_with)
        return ref.id

    async def events(self, event_type: str) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            rows = await session.execute(
                text("SELECT payload FROM events.events WHERE type = :t ORDER BY seq"), {"t": event_type}
            )
            return [dict(r[0]) for r in rows.all()]


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def harness(database: Database, tmp_path: Path, clock: FixedClock) -> MkHarness:
    ev = make_events(database, tmp_path / "blobs", clock)
    await ev.full.authz.catalog.sync()
    ev.module.register()
    capabilities = ev.full.identity.capabilities
    economy = GamificationModule(
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
    economy.register()
    await economy.levels.ensure_default()
    module = MarketplaceModule(
        database,
        ev.publisher,
        ev.full.authz.audit,
        capabilities,
        ev.full.authz.engine,
        clock=clock,
        event_types=ev.types,
        observables=ObservableRegistry(),
        product_types=ProductTypeRegistry(),
        widgets=WidgetRegistry(),
        search=SearchRegistry(),
        tools=AIToolRegistry(),
        sections=SectionRegistry(),
    )
    module.register()
    return MkHarness(ev, module, economy, clock)


@pytest.fixture
def app(harness: MkHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = harness.ev.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        gamification=harness.economy,
        marketplace=harness.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http


@pytest.fixture
async def mk(harness: MkHarness, app: FastAPI) -> MkHarness:
    """``boss`` (admin), ``ursula``, ``ulrich`` and ``vera`` (users)."""
    from tests.authz_fixtures import make_admin
    from tests.integration.identity.helpers import create_user, module_of

    harness.people = {
        name: await create_user(module_of(app), name) for name in ("boss", "ursula", "ulrich", "vera")
    }
    await make_admin(harness.ev.full, harness.people["boss"])
    return harness


@dataclass
class FakeQuota:
    """024 ``RequestQuotaService`` as Marketplace sees it: extra units only, consumption elsewhere."""

    units: dict[UUID, int] = field(default_factory=dict)
    seen: set[str] = field(default_factory=set)

    async def available(self, user: UUID) -> dict[str, int]:
        return {"base_limit": 5, "base_used": 0, "base_remaining": 5, "extra_units": self.units.get(user, 0)}

    async def add_units(self, user: UUID, units: int, source_ref: str, idempotency_key: str) -> int:
        if idempotency_key not in self.seen:
            self.seen.add(idempotency_key)
            self.units[user] = self.units.get(user, 0) + units
        return self.units[user]

    async def remove_units(self, user: UUID, units: int, source_ref: str, idempotency_key: str) -> int:
        if idempotency_key not in self.seen:
            self.seen.add(idempotency_key)
            self.units[user] = max(0, self.units.get(user, 0) - units)
        return self.units[user]


def product_def(key: str, kind: str = "badge", **version: Any) -> dict[str, Any]:
    payload = {
        "badge": {"label": "Night owl"},
        "widget": {"widget": "test.widget"},
        "quota": {"kind": "media_requests", "units": 3},
    }
    body: dict[str, Any] = {
        "names": {"en": key.replace("_", " ").title(), "fr": key},
        "payload": payload.get(kind, {}),
    }
    body.update(version)
    return {"key": key, "type": kind, "version": body}


async def published(mk: "MkHarness", key: str, kind: str = "badge", **version: Any) -> str:
    await mk.module.catalog.create(mk.p("boss"), product_def(key, kind, **version))
    await mk.module.catalog.move(mk.p("boss"), key, "available")
    return key


async def confirmed(
    client: httpx.AsyncClient, method: str, path: str, body: dict[str, Any]
) -> httpx.Response:
    first = await client.request(method, path, json=body)
    if first.status_code != 409 or first.json().get("code") != "authz.confirmation_required":
        return first
    return await client.request(method, path, json={**body, "confirmation": first.json()["confirmation"]})
