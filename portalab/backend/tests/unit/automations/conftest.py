"""Reuses the automation integration fixtures (real PostgreSQL, event store, engine, users)."""

from tests.integration.automations.conftest import app, au, client, clock, harness  # noqa: F401 — fixtures
from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
