"""003 T034 — upgrade from the spec 002 schema (identity, with an account) to authz + audit."""

import asyncio
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.pool import NullPool

from portalab.app.migrations import current_heads, upgrade
from portalab.core.db import Database


async def test_upgrade_from_002_keeps_accounts(empty_db_url: str, heads: set[str]) -> None:
    for target in ("core_0005", "identity_0001"):  # the 002 release
        await asyncio.to_thread(upgrade, empty_db_url, target)
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    user_id = uuid4()
    try:
        async with db.engine.begin() as conn:
            assert (await conn.execute(text("SELECT to_regnamespace('authz')"))).scalar() is None
            await conn.execute(
                text(
                    "INSERT INTO identity.users (id, login, display_name, display_name_key, state, "
                    "transition_seq, "
                    "state_changed_at, created_at, updated_at) "
                    "VALUES (:id, 'keep', 'Keep', 'keep', 'active', 1, now(), now(), now())"
                ),
                {"id": user_id},
            )
        await asyncio.to_thread(upgrade, empty_db_url)
        assert await current_heads(db) == heads
        async with db.engine.connect() as conn:
            assert (await conn.execute(text("SELECT login FROM identity.users"))).scalar_one() == "keep"
            assert (await conn.execute(text("SELECT count(*) FROM authz.roles"))).scalar() == 5
            assert (
                await conn.execute(text("SELECT current_admin_user_id FROM authz.admin_singleton"))
            ).one() == (None,)
            assert (await conn.execute(text("SELECT count(*) FROM audit.audit_entries"))).scalar() == 0
    finally:
        await db.dispose()
