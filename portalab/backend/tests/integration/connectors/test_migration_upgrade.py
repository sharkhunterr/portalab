"""005 T039 — upgrade from the 007 release (events) to the connectors schema, keeping existing data."""

import asyncio

from sqlalchemy import text
from sqlalchemy.pool import NullPool

from portalab.app.migrations import current_heads, upgrade
from portalab.core.db import Database


async def test_upgrade_from_007(empty_db_url: str, heads: set[str]) -> None:
    for target in (
        "core_0005",
        "identity_0001",
        "authz_0001",
        "audit_0002",
        "privacy_0001",
        "administration_0001",
        "events_0001",
    ):
        await asyncio.to_thread(upgrade, empty_db_url, target)
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    try:
        async with db.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO admin.extension_toggles (id, kind, ref, enabled, changed_at, reason) "
                    "VALUES (gen_random_uuid(), 'connector', 'fake', true, now(), 'before 005')"
                )
            )
        await asyncio.to_thread(upgrade, empty_db_url)
        assert await current_heads(db) == heads
        async with db.engine.connect() as conn:
            tables = set(
                (
                    await conn.execute(
                        text("SELECT tablename FROM pg_tables WHERE schemaname = 'connectors'")
                    )
                ).scalars()
            )
            kept = (
                await conn.execute(text("SELECT reason FROM admin.extension_toggles WHERE ref = 'fake'"))
            ).scalar()
        assert {"services", "sync_runs", "sync_state"} <= tables and kept == "before 005"
    finally:
        await db.dispose()
