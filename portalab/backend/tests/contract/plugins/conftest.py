"""Reuses the plugin integration fixtures (real PostgreSQL, event store, plugins module, users)."""

from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
from tests.integration.plugins.conftest import app, client, clock, harness, pl  # noqa: F401 — fixtures
