"""Reuses the gamification integration fixtures (real PostgreSQL, event store, module, users)."""

from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
from tests.integration.gamification.conftest import app, client, clock, gm, harness  # noqa: F401 — fixtures
