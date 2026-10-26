"""020 T033 (F18) — dynamic validation (e.g. widget keys known at runtime), toggle dependency checks delegated
to a hook (023's ModuleRegistry), plugin-scope settings declared from manifests."""

import pytest

from portalab.core.config_declaration import default_catalog
from portalab.core.errors import ValidationFailed
from tests.authz_fixtures import insert_user, user
from tests.privacy_fixtures import FullPlatform

OWNER = "test:dynamic"


async def test_dynamic_validator_and_plugin_settings(full: FullPlatform) -> None:
    registry = full.administration.registry
    default_catalog.declare(
        scope="global", key="testkit.widgetPolicies", schema=dict[str, str], default={}, owner=OWNER
    )
    known_widgets = {"services.status", "media.recent"}

    async def validate(value: dict[str, str]) -> list[str]:
        return [f"unknown widget {key}" for key in value if key not in known_widgets]

    registry.register_validator("testkit.widgetPolicies", validate, owner=OWNER)
    admin = user(await insert_user(full.database))
    try:
        await full.administration.config.set(
            "testkit.widgetPolicies", {"media.recent": "pinned"}, actor=admin
        )
        with pytest.raises(ValidationFailed, match="unknown widget"):
            await full.administration.config.set("testkit.widgetPolicies", {"ghost": "pinned"}, actor=admin)
        keys = registry.declare_plugin_settings(
            "weather", [{"key": "units", "type": "string", "default": "metric"}]
        )
        await full.administration.config.set(
            keys[0], "imperial", scope="plugin", scope_ref="weather", actor=admin
        )
        assert (await full.administration.config.get(keys[0])).value == "imperial"
    finally:
        registry.unregister(OWNER)
        registry.unregister("plugin:weather")


async def test_settings_read_at_once_for_a_refresh(full: FullPlatform) -> None:
    """Every module's configuration refreshed from one read of the settings — the same values as one by one,
    a user's own value still read as asked, and a change made after it seen again."""
    config = full.administration.config
    admin = user(await insert_user(full.database))
    await config.set("identity.dormancyDays", 400, actor=admin)
    one_by_one = (await config.get("identity.dormancyDays")).value
    async with config.read_at_once():
        assert (await config.get("identity.dormancyDays")).value == one_by_one == 400
        assert (await config.get("privacy.minAggregateSize")).value == (
            default_catalog.get("privacy.minAggregateSize").default
        )
    await config.set("identity.dormancyDays", 401, actor=admin)
    assert (await config.get("identity.dormancyDays")).value == 401
