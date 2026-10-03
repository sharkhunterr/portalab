"""Reuses the marketplace integration fixtures (real PostgreSQL, event store, economy, users)."""

from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
from tests.integration.marketplace.conftest import app, client, clock, harness, mk  # noqa: F401 — fixtures
