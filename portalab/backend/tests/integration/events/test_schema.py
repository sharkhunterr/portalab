"""007 T004 — partitioned ``events.events`` (by retention class then month) accepts inserts, rejects
UPDATE/DELETE; unique (type, dedup_key); unique (consumer, event_id) deliveries."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from portalab.core.db import Database

INSERT = text(
    "INSERT INTO events.events (event_id, retention_class, occurred_at, type, type_version, received_at, "
    "source_system, actor_kind, payload, provenance, visibility_class) "
    "VALUES (:id, :klass, :at, 't.x', 1, now(), 'test', 'system', '{}', '{}', 'private')"
)


async def test_partition_routing_and_append_only(database: Database) -> None:
    now = datetime.now(UTC)
    rows = {}
    async with database.engine.begin() as conn:
        for klass, when in (
            ("business", now),
            ("technical", now),
            ("business", datetime(2001, 1, 1, tzinfo=UTC)),
        ):
            event_id = uuid4()
            await conn.execute(INSERT, {"id": event_id, "klass": klass, "at": when})
            rows[event_id] = (klass, when)
        located = dict(
            (await conn.execute(text("SELECT event_id, tableoid::regclass::text FROM events.events"))).all()
        )
    for event_id, (klass, when) in rows.items():
        expected = (
            f"events.events_{klass}_p{when:%Y%m}" if when.year > 2020 else f"events.events_{klass}_pdefault"
        )
        assert located[event_id] == expected
    for statement in ("UPDATE events.events SET type = 'x'", "DELETE FROM events.events"):
        with pytest.raises(DBAPIError, match="append-only"):
            async with database.engine.begin() as conn:
                await conn.execute(text(statement))


async def test_unique_constraints(database: Database) -> None:
    dedup = text("INSERT INTO events.dedup_keys VALUES ('t.x', 'k', :id, now())")
    delivery = text(
        "INSERT INTO events.deliveries (consumer, event_id, event_seq, status, attempts, updated_at) "
        "VALUES ('c', :id, 1, 'pending', 0, now())"
    )
    event_id = uuid4()
    async with database.engine.begin() as conn:
        await conn.execute(dedup, {"id": uuid4()})
        await conn.execute(delivery, {"id": event_id})
    for statement, params in ((dedup, {"id": uuid4()}), (delivery, {"id": event_id})):
        with pytest.raises(IntegrityError):
            async with database.engine.begin() as conn:
                await conn.execute(statement, params)
