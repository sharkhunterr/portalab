"""005 T004 — connectors schema: tables, constraints, immutable sync history, unique service+capability."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from portalab.core.db import Database

TABLES = {
    "services",
    "service_capabilities",
    "sync_state",
    "sync_runs",
    "discovery_candidates",
    "compatibility_checks",
}

INSERT_SERVICE = text(
    "INSERT INTO connectors.services (id, connector_key, name, config, credentials, state, state_seq, "
    "state_changed_at, created_at, updated_at) "
    "VALUES (:id, 'fake', 'x', '{}', '{}', :state, 0, now(), now(), now())"
)
INSERT_RUN = text(
    "INSERT INTO connectors.sync_runs (id, service_id, kind, started_at, finished_at, status, added, "
    "modified, removed, ignored, errored, partial) "
    "VALUES (:id, :sid, 'manual', now(), now(), 'succeeded', 1, 0, 0, 0, 0, false)"
)


async def test_tables_exist(database: Database) -> None:
    async with database.engine.connect() as conn:
        found = set(
            (
                await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'connectors'"))
            ).scalars()
        )
    assert found >= TABLES


async def test_state_is_constrained(database: Database) -> None:
    with pytest.raises(IntegrityError):
        async with database.engine.begin() as conn:
            await conn.execute(INSERT_SERVICE, {"id": uuid4(), "state": "exploded"})


async def test_unique_service_capability(database: Database) -> None:
    service_id = uuid4()
    async with database.engine.begin() as conn:
        await conn.execute(INSERT_SERVICE, {"id": service_id, "state": "configured"})
    insert = text(
        "INSERT INTO connectors.service_capabilities (id, service_id, capability, enabled, priority) "
        "VALUES (:id, :sid, 'demo.items', true, 100)"
    )
    async with database.engine.begin() as conn:
        await conn.execute(insert, {"id": uuid4(), "sid": service_id})
    with pytest.raises(IntegrityError):
        async with database.engine.begin() as conn:
            await conn.execute(insert, {"id": uuid4(), "sid": service_id})


async def test_sync_runs_rows_are_immutable(database: Database) -> None:
    service_id, run_id = uuid4(), uuid4()
    async with database.engine.begin() as conn:
        await conn.execute(INSERT_SERVICE, {"id": service_id, "state": "enabled"})
        await conn.execute(INSERT_RUN, {"id": run_id, "sid": service_id})
    for statement in (
        "UPDATE connectors.sync_runs SET added = 99",
        "TRUNCATE connectors.sync_runs",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            async with database.engine.begin() as conn:
                await conn.execute(text(statement))
    async with database.engine.begin() as conn:  # only the retention window deletes
        await conn.execute(text("DELETE FROM connectors.sync_runs WHERE id = :id"), {"id": run_id})
