"""003 T037 (F20) — owner-tagged permission registrations: unregister(owner) removes exactly that owner's
contributions (spec 023 conformance sweep)."""

import pytest

from portalab.core.permissions import PermissionRegistry

pytestmark = pytest.mark.unit


def test_unregister_owner() -> None:
    registry = PermissionRegistry()
    registry.declare("tickets.create", "Open tickets", owner="module:support")
    registry.declare("plugin:weather.use", "Weather", owner="plugin:weather")
    registry.declare("plugin:weather.admin", "Weather admin", owner="plugin:weather")
    assert registry.unregister("plugin:weather") == 2
    assert registry.keys() == {"tickets.create"}
    assert registry.unregister("plugin:weather") == 0
    assert registry.get("tickets.create") is not None
