"""AI tests reuse the integration fixtures (real PostgreSQL, the AI module, scripted provider)."""

from tests.integration.ai.conftest import ai, app, client, clock, people  # noqa: F401 — fixtures
from tests.integration.conftest import (  # noqa: F401 — fixtures
    admin_url,
    database,
    empty_db_url,
    heads,
    migrated_db_url,
    migrated_template,
)
