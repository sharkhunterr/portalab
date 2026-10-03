"""Media tests reuse the integration fixtures (real PostgreSQL)."""

from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
from tests.integration.media.conftest import app, client, clock, media  # noqa: F401 — fixtures
