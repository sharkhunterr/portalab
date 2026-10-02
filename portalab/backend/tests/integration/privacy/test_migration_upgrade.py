"""021 T040 — upgrade from the 003 release with audit data: rows move into monthly partitions keeping their
``seq``; the identity sequence continues after them; privacy schema created."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.pool import NullPool

from portalab.app.migrations import current_heads, upgrade
from portalab.core.db import Database


async def test_upgrade_from_003_partitions_existing_audit(empty_db_url: str, heads: set[str]) -> None:
    for target in ("core_0005", "identity_0001", "authz_0001", "audit_0001"):  # the 003 release
        await asyncio.to_thread(upgrade, empty_db_url, target)
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    try:
        async with db.engine.begin() as conn:
            for when in (datetime(2026, 8, 15, tzinfo=UTC), datetime(2026, 9, 20, tzinfo=UTC)):
                await conn.execute(
                    text(
                        "INSERT INTO audit.audit_entries (id, occurred_at, received_at, actor_kind, action, "
                        "decision, result) VALUES (:id, :at, :at, 'system', 'legacy', 'n/a', 'n/a')"
                    ),
                    {"id": uuid4(), "at": when},
                )
            before = (
                (await conn.execute(text("SELECT seq FROM audit.audit_entries ORDER BY seq"))).scalars().all()
            )
        await asyncio.to_thread(upgrade, empty_db_url)
        assert await current_heads(db) == heads
        async with db.engine.begin() as conn:
            rows = (
                await conn.execute(
                    text("SELECT seq, tableoid::regclass::text FROM audit.audit_entries ORDER BY seq")
                )
            ).all()
            assert [row.seq for row in rows] == before
            assert [row.tableoid for row in rows] == [
                "audit.audit_entries_p202608",
                "audit.audit_entries_p202609",
            ]
            await conn.execute(
                text(
                    "INSERT INTO audit.audit_entries (id, occurred_at, received_at, actor_kind, action, "
                    "decision, "
                    "result) VALUES (:id, now(), now(), 'system', 'new', 'n/a', 'n/a')"
                ),
                {"id": uuid4()},
            )
            newest = (await conn.execute(text("SELECT max(seq) FROM audit.audit_entries"))).scalar()
            assert newest > max(before)
            assert (
                await conn.execute(text("SELECT count(*) FROM privacy.visibility_policies"))
            ).scalar() == 0
    finally:
        await db.dispose()
