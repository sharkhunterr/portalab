"""Automation integration fixtures: the engine on the real event store with isolated registries, a fake
owner action recording its calls, test event types flagged ``automatable``, a fixed clock and real users."""

import asyncio
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

from portalab.capabilities.automation_actions import ActionRegistry, ActionType, current_action
from portalab.capabilities.automations import ConditionRegistry
from portalab.capabilities.events import EventType
from portalab.capabilities.observability import ObservableRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.logging import get_correlation_id
from portalab.core.time import FixedClock
from portalab.modules.automations.module import AutomationsModule
from tests.events_fixtures import EventsHarness, make_events
from tests.integration.privacy.conftest import NOW


class Happened(BaseModel):
    value: int = 0
    label: str = ""
    starts_at: str | None = None


@dataclass
class Recorder:
    """A fake owner action: records params, principal, chain and depth of each call."""

    calls: list[dict[str, Any]] = field(default_factory=list)
    fail: bool = False
    delay: float = 0.0

    async def __call__(self, params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        context = current_action()
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("owner domain failed")
        self.calls.append(
            {
                "params": dict(params),
                "principal": principal,
                "chain": get_correlation_id(),
                "depth": context.depth if context else None,
            }
        )
        return {"recorded": len(self.calls), "body": "x" * 500}


@dataclass
class AutoHarness:
    ev: EventsHarness
    module: AutomationsModule
    actions: ActionRegistry
    conditions: ConditionRegistry
    clock: FixedClock
    record: Recorder
    people: dict[str, UUID] = field(default_factory=dict)

    @property
    def database(self) -> Database:
        return self.ev.full.database

    def p(self, name: str) -> Principal:
        return Principal(user_id=self.people[name])

    async def automation(self, key: str, definition: Mapping[str, Any], *, author: str = "boss") -> UUID:
        row = await self.module.definitions.create(self.p(author), key, definition)
        await self.module.definitions.publish(self.p(author), row.id)
        return row.id

    async def emit(
        self,
        payload: Mapping[str, Any] | None = None,
        *,
        event_type: str = "test.happened",
        actor: str | None = "ursula",
        correlation: str | None = None,
    ) -> None:
        from portalab.core.logging import correlation_scope

        with correlation_scope(correlation):
            async with self.database.unit_of_work() as uow:
                await self.ev.publisher.publish(
                    uow.session,
                    event_type,
                    dict(payload or {"value": 1, "label": "hello"}),
                    occurred_at=self.clock.now(),
                    actor=Principal(user_id=self.people[actor]) if actor else None,
                    source="test",
                )
        await self.dispatch()

    async def dispatch(self) -> None:
        for _ in range(20):
            runs = await self.ev.module.dispatcher.run_once()
            if not any(run.delivered for run in runs):
                return

    async def executions(self, automation: UUID) -> list[Any]:
        return list(reversed(await self.module.history.list(automation)))


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def harness(database: Database, tmp_path: Path, clock: FixedClock) -> AutoHarness:
    ev = make_events(database, tmp_path / "blobs", clock)
    await ev.full.authz.catalog.sync()
    ev.module.register()
    for name in ("test.happened", "test.other"):
        ev.types.register(
            EventType(name, "test:domain", schema=Happened, open_payload=False, automatable=True)
        )
    ev.types.register(EventType("test.quiet", "test:domain", schema=Happened, open_payload=False))
    actions, conditions, record = ActionRegistry(), ConditionRegistry(), Recorder()
    actions.register(
        ActionType(
            key="test.record",
            description="record a call",
            permission="users.self.manage",
            idempotency="test",
            run=record,
            owner="module:test",
            params_schema={"text": "string?", "count": "integer?"},
            ai_output_allowed=True,
        )
    )
    module = AutomationsModule(
        database,
        ev.publisher,
        ev.full.authz.audit,
        ev.full.identity.capabilities,
        ev.full.authz.engine,
        clock=clock,
        event_types=ev.types,
        consumers=ev.consumers,
        actions=actions,
        conditions=conditions,
        observables=ObservableRegistry(),
    )
    module.register()
    return AutoHarness(ev, module, actions, conditions, clock, record)


@pytest.fixture
def app(harness: AutoHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = harness.ev.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        automations=harness.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http


@pytest.fixture
async def au(harness: AutoHarness, app: FastAPI) -> AutoHarness:
    """Users ``boss`` (admin), ``ursula`` and ``ulrich``."""
    from tests.authz_fixtures import make_admin
    from tests.integration.identity.helpers import create_user, module_of

    harness.people = {name: await create_user(module_of(app), name) for name in ("boss", "ursula", "ulrich")}
    await make_admin(harness.ev.full, harness.people["boss"])
    return harness


def basic(**overrides: Any) -> dict[str, Any]:
    definition: dict[str, Any] = {
        "name": "Record happenings",
        "trigger": {"kind": "event", "event_type": "test.happened"},
        "conditions": {"leaf": "event_field", "params": {"field": "value", "op": "gte", "value": 1}},
        "steps": [
            {
                "id": "record",
                "action": "test.record",
                "params": {"text": "value ${event.value} by ${actor.id}"},
            }
        ],
    }
    definition.update(overrides)
    return definition


def later(moment: datetime, **delta: float) -> datetime:
    return moment + timedelta(**delta)
