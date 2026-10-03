"""Reuses the campaign integration fixtures (real PostgreSQL, event store, Campaigns + Gamification)."""

from tests.integration.campaigns.conftest import app, client, clock, cm, harness  # noqa: F401 — fixtures
from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
