"""019 T015 — AI boundary: ``ai.invoke`` output may only flow into actions that accept AI text and are not
sensitive; it can never be a condition input (conditions take no substitution) nor feed a destructive or
sensitive action's params; AI never approves (approvals require a person)."""

from collections.abc import Mapping
from typing import Any

import pytest

from portalab.capabilities.automation_actions import ActionType
from portalab.core.authz_port import Principal
from portalab.core.errors import ValidationFailed
from tests.integration.automations.conftest import AutoHarness, basic

pytestmark = pytest.mark.integration


async def text(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
    return {"text": "drafted"}


def register(au: AutoHarness) -> None:
    au.actions.register(
        ActionType(
            "ai.invoke", "draft", "users.self.manage", "x", text, "module:ai", {"instruction": "string"}
        )
    )
    au.actions.register(
        ActionType("test.plain", "plain", "users.self.manage", "x", text, "module:test", {"text": "string?"})
    )
    au.actions.register(
        ActionType(
            "test.danger",
            "danger",
            "users.self.manage",
            "x",
            text,
            "module:test",
            {"text": "string?"},
            sensitivity="destructive",
            ai_output_allowed=True,
        )
    )


async def test_ai_output_routes(au: AutoHarness) -> None:
    register(au)
    draft = {"id": "draft", "action": "ai.invoke", "params": {"instruction": "Summarize ${event.label}"}}
    ok = basic(
        steps=[draft, {"id": "send", "action": "test.record", "params": {"text": "${steps.draft.text}"}}]
    )
    assert au.module.definitions.validate(ok)
    for target in ("test.plain", "test.danger"):
        bad = basic(steps=[draft, {"id": "use", "action": target, "params": {"text": "${steps.draft.text}"}}])
        with pytest.raises(ValidationFailed) as raised:
            au.module.definitions.validate(bad)
        assert any("AI output cannot feed" in e for e in raised.value.extensions["errors"])
    condition = basic(
        conditions={
            "leaf": "event_field",
            "params": {"field": "label", "op": "eq", "value": "${steps.draft.text}"},
        },
        steps=[draft],
    )
    with pytest.raises(ValidationFailed) as raised:
        au.module.definitions.validate(condition)
    assert any("substitution is not allowed in conditions" in e for e in raised.value.extensions["errors"])
