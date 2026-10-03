"""Reuses the community integration fixtures (real PostgreSQL, event store, module, users)."""

from tests.integration.community.conftest import app, client, clock, co, harness  # noqa: F401 — fixtures
from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
