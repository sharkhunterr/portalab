"""020 T035 — upgrade from the 021 release to the administration schemas."""

import asyncio

from sqlalchemy import text
from sqlalchemy.pool import NullPool

from portalab.app.migrations import current_heads, upgrade
from portalab.core.db import Database


async def test_upgrade_from_021(empty_db_url: str, heads: set[str]) -> None:
    for target in (
        "core_0005",
        "identity_0001",
        "authz_0001",
        "audit_0002",
        "privacy_0001",
    ):  # the 021 release
        await asyncio.to_thread(upgrade, empty_db_url, target)
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    try:
        async with db.engine.begin() as conn:
            assert (await conn.execute(text("SELECT to_regnamespace('config')"))).scalar() is None
        await asyncio.to_thread(upgrade, empty_db_url)
        assert await current_heads(db) == heads
        async with db.engine.connect() as conn:
            assert (
                await conn.execute(text("SELECT count(*) FROM admin.first_run WHERE completed_at IS NULL"))
            ).scalar() == 1
            assert (await conn.execute(text("SELECT count(*) FROM config.settings"))).scalar() == 0
    finally:
        await db.dispose()
