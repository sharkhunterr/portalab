"""019 T005 — schema: tables, the unique execution key ``(automation, version, trigger event)``, append-only
versions, FKs only intra-module or to ``identity.users``."""

import pytest
from sqlalchemy import text

from tests.integration.automations.conftest import AutoHarness, basic

pytestmark = pytest.mark.integration


async def test_schema(au: AutoHarness) -> None:
    automation = await au.automation("records", basic())
    async with au.database.session() as session:
        tables = set(
            (
                await session.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'automations'")
                )
            ).scalars()
        )
        foreign = set(
            (
                await session.execute(
                    text(
                        "SELECT confrelid::regclass::text FROM pg_constraint c JOIN pg_namespace n "
                        "ON n.oid = c.connamespace WHERE n.nspname = 'automations' AND contype = 'f'"
                    )
                )
            ).scalars()
        )
    assert {
        "automations",
        "versions",
        "executions",
        "approvals",
        "schedule_state",
        "dedup_windows",
        "pending_fires",
    } <= tables
    assert all(f == "identity.users" or f.startswith("automations.") for f in foreign)
    async with au.database.session() as session:
        with pytest.raises(Exception, match="append-only"):
            await session.execute(text("UPDATE automations.versions SET version = 7"))
    insert = (
        "INSERT INTO automations.executions (id, automation_id, version, trigger_event_id, trigger_ref, "
        "chain_id, depth, status, conditions_trace, steps, batch_count, principal, started_at) "
        "VALUES (gen_random_uuid(), :a, 1, "
        "'00000000-0000-7000-8000-000000000001', '{}', 'c', 0, 'success', '[]', '[]', 1, '{}', now())"
    )
    async with au.database.session() as session:
        await session.execute(text(insert), {"a": automation})
        with pytest.raises(Exception, match="uq_executions_trigger"):
            await session.execute(text(insert), {"a": automation})
