"""020 T005/T034 — declarations: duplicate keys rejected, schema/default validated, sensitive recorded;
owner-tagged registrations disappear with ``unregister(owner)``; plugin-manifest settings (F18)."""

import pytest

from portalab.capabilities.config import SettingUpgrade
from portalab.core.config_declaration import SettingCatalog, SettingDeclarationError
from portalab.modules.administration.config.registry import SettingRegistry, UnknownSetting, allowed_scopes

pytestmark = pytest.mark.unit


def _registry() -> SettingRegistry:
    return SettingRegistry(SettingCatalog())


def test_declarations_are_validated() -> None:
    registry = _registry()
    registry.catalog.declare(scope="global", key="demo.size", schema=int, default=3)
    with pytest.raises(SettingDeclarationError):
        registry.catalog.declare(scope="global", key="demo.size", schema=int, default=3)
    with pytest.raises(SettingDeclarationError):
        registry.catalog.declare(scope="global", key="demo.bad", schema=int, default="x")
    secret = registry.catalog.declare(
        scope="global", key="demo.token", schema=str, default=None, sensitive=True
    )
    assert secret.sensitive
    with pytest.raises(UnknownSetting):
        registry.declaration("demo.missing")


def test_allowed_scopes() -> None:
    registry = _registry()
    plain = registry.catalog.declare(scope="global", key="a.b", schema=int, default=1)
    mod = registry.catalog.declare(scope="module", key="m.x", schema=int, default=1, user_overridable=True)
    user = registry.catalog.declare(scope="user", key="u.y", schema=int, default=1)
    assert allowed_scopes(plain) == {"global"}
    assert allowed_scopes(mod) == {"global", "module", "user"}
    assert allowed_scopes(user) == {"global", "user"}


def test_upgrades_and_owner_unregister() -> None:
    registry = _registry()
    registry.catalog.declare(scope="global", key="w.v", schema=str, default="x", version=3, owner="plugin:w")
    registry.register_upgrade(SettingUpgrade("w.v", 1, lambda v: v + "1"), owner="plugin:w")
    registry.register_upgrade(SettingUpgrade("w.v", 2, lambda v: v + "2"), owner="plugin:w")
    assert registry.upgrade("w.v", "a", 1, 3) == "a12"
    with pytest.raises(LookupError):
        registry.upgrade("w.v", "a", 0, 3)  # never a silent reset
    keys = registry.declare_plugin_settings("w", [{"key": "units", "type": "string", "default": "metric"}])
    assert keys == ["plugin_w.units"]
    assert registry.unregister("plugin:w") == 4
    assert [d.key for d in registry.all()] == []
