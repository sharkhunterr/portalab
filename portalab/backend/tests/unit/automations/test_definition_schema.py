"""019 T004 — closed definitions: max steps; unknown triggers, conditions or actions rejected; params checked
against the action's declared params (required, unknown); substitution only of declared attributes;
condition depth ≤ 3; secret-looking params rejected; no cron strings."""

from typing import Any

import pytest

from portalab.core.errors import ValidationFailed
from tests.integration.automations.conftest import AutoHarness, basic

pytestmark = pytest.mark.integration


def errors(au: AutoHarness, definition: dict[str, Any]) -> list[str]:
    with pytest.raises(ValidationFailed) as raised:
        au.module.definitions.validate(definition)
    assert raised.value.code == "automation.invalid_definition"
    return list(raised.value.extensions["errors"])


def deep(level: int) -> dict[str, Any]:
    node: dict[str, Any] = {"leaf": "event_field", "params": {"field": "value", "op": "eq", "value": 1}}
    for _ in range(level):
        node = {"all_of": [node]}
    return node


async def test_valid_and_invalid(au: AutoHarness) -> None:
    assert au.module.definitions.validate(basic()).steps[0].action == "test.record"
    cases = [
        (basic(trigger={"kind": "event", "event_type": "test.quiet"}), "not an automatable"),
        (basic(trigger={"kind": "event", "event_type": "nothing.here"}), "not an automatable"),
        (basic(trigger={"kind": "cron", "expression": "* * * * *"}), "trigger"),
        (
            basic(
                trigger={
                    "kind": "event",
                    "event_type": "test.happened",
                    "filter": [{"field": "secret", "value": 1}],
                }
            ),
            "undeclared attribute",
        ),
        (basic(conditions={"leaf": "telepathy"}), "unknown condition"),
        (
            basic(conditions={"leaf": "event_field", "params": {"field": "nope", "op": "eq", "value": 1}}),
            "undeclared attribute",
        ),
        (
            basic(conditions={"leaf": "event_field", "params": {"field": "value", "expression": "1==1"}}),
            "unknown params",
        ),
        (basic(conditions=deep(4)), "nest at most"),
        (basic(steps=[{"id": "x", "action": "unknown.action"}]), "unknown action"),
        (basic(steps=[{"id": "x", "action": "test.record", "params": {"extra": 1}}]), "unknown params"),
        (
            basic(steps=[{"id": "x", "action": "test.record", "params": {"text": "${event.nope}"}}]),
            "undeclared reference",
        ),
        (
            basic(steps=[{"id": "x", "action": "test.record", "params": {"text": "${env.path}"}}]),
            "undeclared reference",
        ),
        (
            basic(
                steps=[{"id": "x", "action": "test.record", "params": {"text": "${steps.later.recorded}"}}]
            ),
            "not an earlier step",
        ),
        (basic(steps=[{"id": f"s{i}", "action": "test.record"} for i in range(11)]), "at most 10"),
        (
            basic(steps=[{"id": "x", "action": "test.record", "params": {"text": "${event.value"}}]),
            "invalid substitution",
        ),
    ]
    for definition, fragment in cases:
        assert any(fragment in e for e in errors(au, definition)), (fragment, definition)
    au.actions.get("test.record")  # registered by the harness
    from portalab.capabilities.automation_actions import ActionType

    au.actions.register(
        ActionType(
            "test.secret", "x", "users.self.manage", "x", au.record, "module:test", {"api_key": "string?"}
        )
    )
    assert any(
        "secret-looking" in e
        for e in errors(au, basic(steps=[{"id": "x", "action": "test.secret", "params": {"api_key": "k"}}]))
    )
    au.actions.register(
        ActionType(
            "test.needs", "x", "users.self.manage", "x", au.record, "module:test", {"target": "string"}
        )
    )
    assert any("missing params" in e for e in errors(au, basic(steps=[{"id": "x", "action": "test.needs"}])))
