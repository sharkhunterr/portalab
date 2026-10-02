"""Reuse the privacy integration fixtures (real PostgreSQL, full platform)."""

from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
from tests.integration.privacy.conftest import app, client, clock, full  # noqa: F401 — fixtures
