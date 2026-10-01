"""Alembic environment (async, asyncpg). Version table: ``core.schema_version``.

Each module contributes ``migrations/<module>/versions`` with its own branch label; plugins use separate
branch labels (spec 023). All schemas are included so autogenerate sees every module.
"""

import asyncio

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from portalab.app.composition import import_all_models
from portalab.app.migrations import VERSION_SCHEMA, VERSION_TABLE
from portalab.core.db import all_metadata
from portalab.core.settings import load_settings

config = context.config
import_all_models()
target_metadata = all_metadata()


def _database_url() -> str:
    url = config.attributes.get("database_url")
    return str(url) if url else load_settings().database_url.reveal()


def _run(connection: Connection) -> None:
    connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{VERSION_SCHEMA}"'))
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table=VERSION_TABLE,
        version_table_schema=VERSION_SCHEMA,
        compare_type=True,
        transaction_per_migration=False,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = create_async_engine(_database_url(), poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(_run)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("offline (SQL script) migrations are not supported; run 'portalab migrate'")
asyncio.run(_run_online())
