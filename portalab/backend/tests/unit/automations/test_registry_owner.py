"""019 T036 (F20) — owner-tagged registries: every action and condition of an owner disappears with
``unregister(owner)``; plugins may not add condition operators; a key belongs to one owner."""

from collections.abc import Mapping
from typing import Any

import pytest

from portalab.capabilities.automation_actions import ActionRegistry, ActionType
from portalab.capabilities.automations import ConditionLeaf, ConditionRegistry, LeafContext
from portalab.core.authz_port import Principal


async def run(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
    return {}


async def leaf(ctx: LeafContext, params: Mapping[str, Any]) -> bool | None:
    return True


def test_owners() -> None:
    actions = ActionRegistry()
    actions.register(ActionType("plugin:demo.one", "x", "users.self.manage", "x", run, "plugin:demo"))
    actions.register(ActionType("plugin:demo.two", "x", "users.self.manage", "x", run, "plugin:demo"))
    actions.register(ActionType("media.request", "x", "users.self.manage", "x", run, "module:media"))
    with pytest.raises(ValueError, match="already registered"):
        actions.register(ActionType("media.request", "x", "users.self.manage", "x", run, "plugin:demo"))
    assert actions.unregister("plugin:demo") == 2 and [a.key for a in actions.all()] == ["media.request"]
    conditions = ConditionRegistry()
    conditions.register(ConditionLeaf("weather_is", "x", leaf, owner="module:health"))
    with pytest.raises(ValueError, match="plugins contribute"):
        conditions.register(ConditionLeaf("plugin_op", "x", leaf, owner="plugin:demo"))
    assert conditions.unregister("module:health") == 1 and conditions.all() == []
