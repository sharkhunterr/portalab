"""006 T026 — upgrade from the 005 release (connectors) to the health schema, keeping existing data."""

import asyncio

from sqlalchemy import text
from sqlalchemy.pool import NullPool

from portalab.app.migrations import current_heads, upgrade
from portalab.core.db import Database


async def test_upgrade_from_005(empty_db_url: str, heads: set[str]) -> None:
    for target in (
        "core_0005",
        "identity_0001",
        "authz_0001",
        "audit_0002",
        "privacy_0001",
        "administration_0001",
        "events_0001",
        "connectors_0001",
    ):
        await asyncio.to_thread(upgrade, empty_db_url, target)
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    try:
        async with db.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO connectors.services (id, connector_key, name, config, credentials, state, "
                    "state_seq, state_changed_at, created_at, updated_at) VALUES (gen_random_uuid(), 'fake', "
                    "'Kept', '{}', '{}', 'enabled', 1, now(), now(), now())"
                )
            )
        await asyncio.to_thread(upgrade, empty_db_url)
        assert await current_heads(db) == heads
        async with db.engine.connect() as conn:
            kept = (await conn.execute(text("SELECT name FROM connectors.services"))).scalar()
            tables = set(
                (
                    await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'health'"))
                ).scalars()
            )
        assert (
            kept == "Kept" and {"service_state", "health_samples_pdefault", "maintenance_windows"} <= tables
        )
    finally:
        await db.dispose()
