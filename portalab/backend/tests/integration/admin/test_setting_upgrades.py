"""020 T032 — stored values written under an older schema version are upgraded on read; a missing upgrade
never silently resets: the next scope / code default is used and the problem is counted."""

import json

from sqlalchemy import text

from portalab.capabilities.config import SettingUpgrade
from portalab.core.config_declaration import default_catalog
from portalab.modules.administration.observability import metrics
from tests.privacy_fixtures import FullPlatform

OWNER = "test:upgrade"


async def test_upgrade_on_read(full: FullPlatform) -> None:
    default_catalog.declare(
        scope="global",
        key="demo.units",
        schema=dict[str, str],
        default={"system": "metric"},
        version=2,
        owner=OWNER,
    )
    full.administration.registry.register_upgrade(
        SettingUpgrade("demo.units", 1, lambda old: {"system": old}), owner=OWNER
    )
    try:
        async with full.database.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO config.settings "
                    "(id, key, scope, scope_ref, value, schema_version, updated_at) "
                    "VALUES (gen_random_uuid(), 'demo.units', 'global', '', CAST(:v AS jsonb), 1, now())"
                ),
                {"v": json.dumps("imperial")},
            )
        assert (await full.administration.config.get("demo.units")).value == {"system": "imperial"}
        full.administration.registry.unregister(OWNER)
        default_catalog.declare(
            scope="global",
            key="demo.units",
            schema=dict[str, str],
            default={"system": "metric"},
            version=2,
            owner=OWNER,
        )
        metrics.reset()
        fallback = await full.administration.config.get("demo.units")
        assert fallback.value == {"system": "metric"} and fallback.source == "default"
        assert metrics.snapshot()["admin.config.invalid_stored_values"] == 1
    finally:
        full.administration.registry.unregister(OWNER)
