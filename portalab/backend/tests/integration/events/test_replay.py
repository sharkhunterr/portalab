"""007 T027/T028 — replay rebuilds a projection deterministically in order, suppresses effects, refuses
non-replay-safe consumers, leaves originals untouched, records the run; API needs a confirmation."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope, EventType
from portalab.core.errors import ValidationFailed
from portalab.modules.events.models import Event, ReplayRun
from tests.authz_fixtures import make_admin, user
from tests.events_fixtures import EventsHarness
from tests.integration.identity.helpers import create_user, login, module_of

T0 = datetime(2026, 9, 1, tzinfo=UTC)


async def _seed(ev: EventsHarness) -> None:
    ev.types.register(EventType("score.added", "t"))
    async with ev.full.database.unit_of_work() as uow:
        # published out of order: replay follows occurred_at
        for minutes, points in ((2, 5), (0, 10), (1, -3)):
            await ev.publisher.publish(
                uow.session, "score.added", {"points": points}, occurred_at=T0 + timedelta(minutes=minutes)
            )


async def test_rebuild(ev: EventsHarness) -> None:
    await _seed(ev)
    totals: list[int] = []
    effects: list[str] = []
    as_of: list[datetime] = []

    async def projection(event: Envelope, ctx: ConsumerContext) -> None:
        totals.append((totals[-1] if totals else 0) + int(event.payload["points"]))
        as_of.append(ctx.as_of)
        if await ctx.idempotent_effect(f"notify:{event.event_id}"):
            effects.append("sent")

    async def notifier(event: Envelope, ctx: ConsumerContext) -> None:
        effects.append("should never run")

    ev.consumers.register(Consumer("scores", frozenset({"score.added"}), projection, "t", replay_safe=True))
    ev.consumers.register(Consumer("notifier", frozenset({"score.added"}), notifier, "t"))
    admin = user(
        await __import__("tests.authz_fixtures", fromlist=["insert_user"]).insert_user(ev.full.database)
    )
    run = await ev.module.replay.rebuild("scores", actor=admin)
    assert totals == [10, 7, 12] and effects == [] and as_of == sorted(as_of)
    assert run.status == "finished" and run.processed == 3
    totals.clear()
    await ev.module.replay.rebuild("scores", actor=admin, from_occurred_at=T0 + timedelta(minutes=1))
    assert totals == [-3, 2]
    with pytest.raises(ValidationFailed):
        await ev.module.replay.rebuild("notifier", actor=admin)
    async with ev.full.database.session() as session:
        assert (
            await session.scalar(select(func.count()).select_from(Event).where(Event.type == "score.added"))
            == 3
        )
        assert await session.scalar(select(func.count()).select_from(ReplayRun)) == 2


async def test_replay_api_needs_confirmation(
    app: FastAPI, client: httpx.AsyncClient, ev: EventsHarness
) -> None:
    app.state.events_module = ev.module
    await _seed(ev)

    async def projection(event: Envelope, ctx: ConsumerContext) -> None:
        return None

    ev.consumers.register(Consumer("scores", frozenset({"score.added"}), projection, "t", replay_safe=True))
    admin_id = await create_user(module_of(app), "boss")
    await make_admin(ev.full, admin_id)
    await login(client, "boss")
    first = await client.post("/api/v1/admin/replay", json={"projection": "scores"})
    assert first.status_code == 409 and first.json()["code"] == "authz.confirmation_required"
    done = await client.post(
        "/api/v1/admin/replay", json={"projection": "scores", "confirmation": first.json()["confirmation"]}
    )
    assert done.status_code == 202 and done.json()["processed"] == 3
