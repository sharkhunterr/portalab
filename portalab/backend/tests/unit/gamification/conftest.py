"""Some guard and definition tests need the database: they reuse the gamification integration fixtures."""

from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
from tests.integration.gamification.conftest import app, clock, gm, harness  # noqa: F401 — fixtures
