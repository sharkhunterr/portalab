"""T062 — upgrade from the previous release with representative data, plus model ↔ migration parity.

Every later spec adds (1) its revision chain and (2) a seeder below that writes representative rows at the
previous-release revision and a check that they survive the upgrade. ``PREVIOUS_RELEASE`` moves forward when
a release is tagged. The parity test guarantees that every mapped model is fully described by migrations.
"""

import asyncio
from collections.abc import Awaitable, Callable

from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.pool import NullPool

from portalab.app.composition import import_all_models
from portalab.app.migrations import VERSION_SCHEMA, VERSION_TABLE, current_heads, upgrade
from portalab.core.db import Database, all_metadata

PREVIOUS_RELEASE = "core_0002"  # first schema containing data (core.job); bump at each tagged release

Seeder = Callable[[AsyncConnection], Awaitable[None]]
Check = Callable[[AsyncConnection], Awaitable[None]]


async def _seed_core(conn: AsyncConnection) -> None:
    await conn.execute(
        text(
            "INSERT INTO core.job (id, queue, kind, payload, dedup_key, status, run_at, attempts, "
            "max_attempts, created_at, updated_at) VALUES (gen_random_uuid(), 'default', 'demo.kind', "
            "'{\"ref\": \"x\"}', 'demo:1', 'queued', now(), 0, 5, now(), now())"
        )
    )


async def _check_core(conn: AsyncConnection) -> None:
    row = (await conn.execute(text("SELECT kind, dedup_key, payload->>'ref' FROM core.job"))).one()
    assert tuple(row) == ("demo.kind", "demo:1", "x")


SEEDERS: list[tuple[Seeder, Check]] = [(_seed_core, _check_core)]


async def test_upgrade_from_previous_release_keeps_data(empty_db_url: str, heads: set[str]) -> None:
    await asyncio.to_thread(upgrade, empty_db_url, PREVIOUS_RELEASE)
    db = Database.from_url(empty_db_url, poolclass=NullPool)
    try:
        async with db.engine.begin() as conn:
            for seed, _ in SEEDERS:
                await seed(conn)
        await asyncio.to_thread(upgrade, empty_db_url)
        assert await current_heads(db) == heads
        async with db.engine.connect() as conn:
            for _, check in SEEDERS:
                await check(conn)
    finally:
        await db.dispose()


def _diff(connection: Connection) -> list[object]:
    context = MigrationContext.configure(
        connection,
        opts={
            "include_schemas": True,
            "version_table": VERSION_TABLE,
            "version_table_schema": VERSION_SCHEMA,
            "compare_type": True,
        },
    )
    # compare every module schema at once (per-schema comparisons report the other schemas' indexes)
    metadatas = [metadata for metadata in all_metadata() if metadata.schema is not None]
    modelled = {table.fullname for metadata in metadatas for table in metadata.tables.values()}
    return [
        diff
        for diff in compare_metadata(context, metadatas)  # type: ignore[arg-type]
        if not (isinstance(diff, tuple) and diff[0] == "remove_table")
        and not _db_only_users_fk(diff)
        and not _unmodelled_table_index(diff, modelled)
    ]


def _unmodelled_table_index(diff: object, modelled: set[str]) -> bool:
    """Indexes of tables that are not modelled (time partitions of ``audit.audit_entries``)."""
    if not (isinstance(diff, tuple) and diff[0] == "remove_index"):
        return False
    return diff[1].table.fullname not in modelled


def _db_only_users_fk(diff: object) -> bool:
    """Other modules reference ``identity.users(id)`` through migration-created FKs only (no cross-module
    model import), so the models legitimately lack them."""
    if not (isinstance(diff, tuple) and diff[0] == "remove_fk"):
        return False
    constraint = diff[1]
    referred = constraint.referred_table
    return (referred.schema, referred.name) == ("identity", "users") and constraint.table.schema != "identity"


async def test_models_and_migrations_are_in_sync(database: Database) -> None:
    import_all_models()
    async with database.engine.connect() as conn:
        diffs = await conn.run_sync(_diff)
    assert diffs == [], f"models differ from migrations, add a revision: {diffs}"
