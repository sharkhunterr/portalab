"""007 T034 — upgrade from the 020 release to the events schema (and the audit ``event_id`` column)."""

import asyncio

from sqlalchemy import text
from sqlalchemy.pool import NullPool

from portalab.app.migrations import current_heads, upgrade
from portalab.core.db import Database


async def test_upgrade_from_020(empty_db_url: str, heads: set[str]) -> None:
    for target in (
        "core_0005",
        "identity_0001",
        "authz_0001",
        "audit_0002",
        "privacy_0001",
        "administration_0001",
    ):
        await asyncio.to_thread(upgrade, empty_db_url, target)
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    try:
        await asyncio.to_thread(upgrade, empty_db_url)
        assert await current_heads(db) == heads
        async with db.engine.connect() as conn:
            partitions = set(
                (
                    await conn.execute(
                        text(
                            "SELECT tablename FROM pg_tables "
                            "WHERE schemaname = 'events' AND tablename LIKE 'events_%'"
                        )
                    )
                ).scalars()
            )
            column = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM information_schema.columns WHERE table_schema = 'audit' "
                        "AND table_name = 'audit_entries' AND column_name = 'event_id'"
                    )
                )
            ).scalar()
        assert {"events_business_pdefault", "events_technical_pdefault"} <= partitions and column == 1
    finally:
        await db.dispose()
