"""T021 — migrations: upgrade from empty succeeds; downgrade is dev-only; /readyz flips after migration."""

import asyncio

import httpx
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from portalab.app.main import create_app
from portalab.app.migrations import current_heads, downgrade, upgrade
from portalab.core.db import Database


async def test_upgrade_from_empty_database(empty_db_url: str, heads: set[str]) -> None:
    await asyncio.to_thread(upgrade, empty_db_url)
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    try:
        assert await current_heads(db) == heads
        async with db.engine.connect() as conn:
            schemas = set(
                (await conn.execute(text("SELECT schema_name FROM information_schema.schemata"))).scalars()
            )
            tables = set(
                (
                    await conn.execute(
                        text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'core'")
                    )
                ).scalars()
            )
        assert "core" in schemas
        assert "schema_version" in tables
    finally:
        await db.dispose()


async def test_upgrade_is_idempotent(empty_db_url: str, heads: set[str]) -> None:
    await asyncio.to_thread(upgrade, empty_db_url)
    await asyncio.to_thread(upgrade, empty_db_url)
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    try:
        assert await current_heads(db) == heads
    finally:
        await db.dispose()


async def test_downgrade_to_base_is_possible_in_development(empty_db_url: str) -> None:
    await asyncio.to_thread(upgrade, empty_db_url)
    await asyncio.to_thread(downgrade, empty_db_url, "base")
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    try:
        assert await current_heads(db) == set()
    finally:
        await db.dispose()


async def test_readyz_flips_to_ready_only_after_migration(empty_db_url: str, heads: set[str]) -> None:
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    app = create_app(database=db, migration_heads=heads)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            before = await client.get("/readyz")
            assert before.status_code == 503
            assert before.json()["code"] == "not_ready.migrations"
            await asyncio.to_thread(upgrade, empty_db_url)
            after = await client.get("/readyz")
            assert after.status_code == 200
            assert after.json() == {"status": "ready"}
    finally:
        await db.dispose()
