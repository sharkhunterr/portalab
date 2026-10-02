"""006 T004 — health schema: tables, partitioned samples, append-only state history, unique rollup bucket."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from portalab.core.db import Database


async def test_tables_and_partitions(database: Database) -> None:
    async with database.engine.connect() as conn:
        tables = set(
            (
                await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'health'"))
            ).scalars()
        )
        partitioned = set(
            (
                await conn.execute(
                    text(
                        "SELECT c.relname FROM pg_partitioned_table p JOIN pg_class c ON c.oid = p.partrelid "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'health'"
                    )
                )
            ).scalars()
        )
    assert {
        "service_state",
        "state_history",
        "health_rollups",
        "recent_errors",
        "maintenance_windows",
    } <= tables
    assert {"health_samples_pdefault", "infra_samples_pdefault"} <= tables
    assert partitioned == {"health_samples", "infra_samples"}


async def test_state_history_is_append_only(database: Database) -> None:
    async with database.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO health.state_history (id, service_id, from_state, to_state, occurred_at, "
                "received_at, reason) VALUES (:id, 's', NULL, 'unknown', now(), now(), 'stale')"
            ),
            {"id": uuid4()},
        )
    for statement in ("UPDATE health.state_history SET reason = 'x'", "DELETE FROM health.state_history"):
        with pytest.raises(DBAPIError, match="append-only"):
            async with database.engine.begin() as conn:
                await conn.execute(text(statement))


async def test_unique_rollup_bucket(database: Database) -> None:
    insert = text(
        "INSERT INTO health.health_rollups (id, service_id, bucket_start, samples, ok_samples, "
        "downtime_seconds) VALUES (:id, 's', '2026-10-01T10:00:00Z', 1, 1, 0)"
    )
    async with database.engine.begin() as conn:
        await conn.execute(insert, {"id": uuid4()})
    with pytest.raises(IntegrityError):
        async with database.engine.begin() as conn:
            await conn.execute(insert, {"id": uuid4()})
