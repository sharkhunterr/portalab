"""Alembic integration: one environment, module-contributed version locations, version table
``core.schema_version``.

Migrations run explicitly (``portalab migrate``), never on the request path (research R14).
"""

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection

from portalab.app.composition import BACKEND_DIR, MIGRATIONS_DIR, migration_locations
from portalab.core.db import Database

VERSION_TABLE = "schema_version"
VERSION_SCHEMA = "core"


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("version_locations", " ".join(migration_locations()))
    config.set_main_option("path_separator", "space")
    config.attributes["database_url"] = database_url
    return config


def expected_heads(database_url: str) -> set[str]:
    return set(ScriptDirectory.from_config(alembic_config(database_url)).get_heads())


def upgrade(database_url: str, revision: str = "heads") -> None:
    command.upgrade(alembic_config(database_url), revision)


def downgrade(database_url: str, revision: str) -> None:
    """Development only — production migrations are forward-only (expand/contract)."""
    command.downgrade(alembic_config(database_url), revision)


def _current_heads(connection: Connection) -> set[str]:
    context = MigrationContext.configure(
        connection, opts={"version_table": VERSION_TABLE, "version_table_schema": VERSION_SCHEMA}
    )
    return set(context.get_current_heads())


async def current_heads(database: Database) -> set[str]:
    async with database.engine.connect() as conn:
        return await conn.run_sync(_current_heads)


async def is_up_to_date(database: Database, heads: set[str]) -> bool:
    try:
        return await current_heads(database) == heads
    except Exception:
        return False
