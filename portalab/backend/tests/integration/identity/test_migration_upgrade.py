"""002 T051 — upgrade from the 001 baseline (``core_0004``) with data to the identity schema."""

import asyncio

from sqlalchemy import text
from sqlalchemy.pool import NullPool

from portalab.app.migrations import current_heads, upgrade
from portalab.core.db import Database

BASELINE_001 = "core_0004"


async def test_upgrade_from_the_001_baseline(empty_db_url: str, heads: set[str]) -> None:
    await asyncio.to_thread(upgrade, empty_db_url, BASELINE_001)
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    try:
        async with db.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO core.job (id, queue, kind, payload, status, run_at, attempts, max_attempts, "
                    "created_at, updated_at) VALUES (gen_random_uuid(), 'default', 'demo.kind', '{}', "
                    "'queued', now(), 0, 5, now(), now())"
                )
            )
            await conn.execute(
                text("INSERT INTO core.live_event (topic, payload, created_at) VALUES ('t', '{}', now())")
            )
            assert (await conn.execute(text("SELECT to_regnamespace('identity')"))).scalar() is None
        await asyncio.to_thread(upgrade, empty_db_url)
        assert await current_heads(db) == heads
        assert {"core_0005", "identity_0004"} <= heads
        async with db.engine.connect() as conn:
            assert (await conn.execute(text("SELECT count(*) FROM core.job"))).scalar() == 1
            assert (await conn.execute(text("SELECT count(*) FROM core.live_event"))).scalar() == 1
            assert (await conn.execute(text("SELECT count(*) FROM identity.users"))).scalar() == 0
            assert (await conn.execute(text("SELECT count(*) FROM core.event_outbox"))).scalar() == 0
    finally:
        await db.dispose()
