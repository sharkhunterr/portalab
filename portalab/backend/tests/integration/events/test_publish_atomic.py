"""007 T009/T012 — publish is atomic with the producer's state; concurrent duplicates store one event;
``occurred_at`` and ``received_at`` are kept apart; invalid input is quarantined, not stored as history."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel
from sqlalchemy import func, select, text

from portalab.capabilities.events import EventType
from portalab.core.authz_port import Principal
from portalab.core.event_port import SubjectRef
from portalab.core.time import FixedClock
from portalab.modules.events.models import Event, Quarantine
from tests.events_fixtures import EventsHarness

OCCURRED = datetime(2026, 9, 30, 21, 0, tzinfo=UTC)


class Synced(BaseModel):
    item_ref: str


async def _count(ev: EventsHarness, model: type) -> int:
    async with ev.full.database.session() as session:
        return int(await session.scalar(select(func.count()).select_from(model)))


async def test_atomic_with_state_and_times(ev: EventsHarness, clock: FixedClock) -> None:
    ev.types.register(EventType("media.synced", "t", schema=Synced, source_id_reliable=True))
    with pytest.raises(RuntimeError):
        async with ev.full.database.unit_of_work() as uow:
            await ev.publisher.publish(
                uow.session,
                "media.synced",
                {"item_ref": "m1"},
                occurred_at=OCCURRED,
                source="plex",
                source_event_id="1",
            )
            raise RuntimeError("producer failed")
    assert await _count(ev, Event) == 0
    clock.advance(timedelta(hours=3))
    async with ev.full.database.unit_of_work() as uow:
        result = await ev.publisher.publish(
            uow.session,
            "media.synced",
            {"item_ref": "m1"},
            occurred_at=OCCURRED,
            source="plex",
            source_event_id="1",
            actor=Principal(user_id=None, channel="system"),
            subject=SubjectRef("media", "m1"),
        )
    async with ev.full.database.session() as session:
        row = await session.get(Event, (result.event_id, "business", OCCURRED))
    assert row is not None and row.occurred_at == OCCURRED and row.received_at == clock.now()
    assert row.actor_kind == "system" and row.subject_id == "m1" and row.type_version == 1


async def test_concurrent_duplicates_store_one_event(ev: EventsHarness) -> None:
    ev.types.register(EventType("media.synced", "t", schema=Synced, source_id_reliable=True))

    async def publish() -> object:
        async with ev.full.database.unit_of_work() as uow:
            return await ev.publisher.publish(
                uow.session,
                "media.synced",
                {"item_ref": "m1"},
                occurred_at=OCCURRED,
                source="plex",
                source_event_id="dup-1",
            )

    results = await asyncio.gather(*(publish() for _ in range(5)))
    assert len({r.event_id for r in results}) == 1  # type: ignore[attr-defined]
    assert sum(r.duplicate for r in results) == 4  # type: ignore[attr-defined]
    assert await _count(ev, Event) == 1


async def test_quarantine(ev: EventsHarness) -> None:
    async with ev.full.database.unit_of_work() as uow:
        unknown = await ev.publisher.publish(uow.session, "nobody.knows", {"x": 1}, occurred_at=OCCURRED)
        personal = await ev.publisher.publish(
            uow.session, "events.quarantined", {"email": "a@b.c"}, occurred_at=OCCURRED
        )
    assert unknown.quarantined and personal.quarantined
    assert await _count(ev, Event) == 0
    async with ev.full.database.session() as session:
        rows = {row.reason: row for row in (await session.execute(select(Quarantine))).scalars()}
    assert set(rows) == {"unknown_type", "pii_detected"}
    assert rows["pii_detected"].raw["metadata"]["email"] == "a@b.c" or "email" in rows["pii_detected"].detail
    async with ev.full.database.engine.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM events.dedup_keys"))).scalar() == 0
