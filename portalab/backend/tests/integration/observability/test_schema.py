"""025 T005 — obs schema: tables, partitioned samples, append-only health history, unique fingerprint."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from portalab.core.db import Database


async def test_schema(database: Database) -> None:
    async with database.engine.connect() as conn:
        tables = set(
            (await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'obs'"))).scalars()
        )
        partitioned = set(
            (
                await conn.execute(
                    text(
                        "SELECT c.relname FROM pg_partitioned_table p JOIN pg_class c ON c.oid = p.partrelid "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'obs'"
                    )
                )
            ).scalars()
        )
    assert {"component_health", "health_history", "rollups", "errors", "anomalies", "contributions"} <= tables
    assert "metric_samples_pdefault" in tables and partitioned == {"metric_samples"}
    assert "incidents" not in tables  # escalation goes to Support's incident system, never a local table


async def test_history_append_only_and_unique_fingerprint(database: Database) -> None:
    async with database.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO obs.health_history (id, component, axis, from_state, to_state, occurred_at, "
                "reason) VALUES (:id, 'events', 'technical', NULL, 'ok', now(), '')"
            ),
            {"id": uuid4()},
        )
    with pytest.raises(DBAPIError, match="append-only"):
        async with database.engine.begin() as conn:
            await conn.execute(text("UPDATE obs.health_history SET reason = 'x'"))
    insert = text(
        "INSERT INTO obs.errors (id, fingerprint, component, category, error_type, level, message, context, "
        "count, first_seen_at, last_seen_at, state) "
        "VALUES (:id, 'fp', 'c', 'cat', 'E', 'error', 'm', '{}', 1, now(), now(), 'open')"
    )
    async with database.engine.begin() as conn:
        await conn.execute(insert, {"id": uuid4()})
    with pytest.raises(IntegrityError):
        async with database.engine.begin() as conn:
            await conn.execute(insert, {"id": uuid4()})
