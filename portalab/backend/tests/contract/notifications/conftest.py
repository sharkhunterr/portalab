"""Notifications tests reuse the integration fixtures (real PostgreSQL)."""

from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
from tests.integration.notifications.conftest import app, client, clock, notify  # noqa: F401 — fixtures
