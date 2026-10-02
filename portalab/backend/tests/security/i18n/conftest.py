"""i18n security tests reuse the integration fixtures (real PostgreSQL)."""

from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
from tests.integration.i18n.conftest import app, client, clock, i18n  # noqa: F401 — fixtures
