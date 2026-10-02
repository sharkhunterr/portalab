"""Administration tests reuse the full-platform fixtures (real PostgreSQL)."""

from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
from tests.integration.privacy.conftest import app, client, clock, full  # noqa: F401 — fixtures
