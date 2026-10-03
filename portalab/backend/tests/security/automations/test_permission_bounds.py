"""019 T012 — no bypass: an action the author cannot perform manually is ``refused``; permissions are
re-evaluated at run time (author deactivated or demoted ⇒ ``refused`` + ``needs_review``); a system
identity is limited to declared scopes ≤ its publisher; ``permission_held`` never grants."""

import pytest
from fastapi import FastAPI

from portalab.capabilities.automation_actions import ActionType
from portalab.core.errors import Forbidden, ValidationFailed
from portalab.modules.identity.domain.state_machine import AccountState
from tests.integration.automations.conftest import AutoHarness, basic
from tests.integration.identity.helpers import module_of, set_state

pytestmark = pytest.mark.integration


async def test_author_rights_bound_every_run(au: AutoHarness, app: FastAPI) -> None:
    au.actions.register(ActionType("test.admin_only", "x", "users.manage", "x", au.record, "module:test"))
    authored_by_user = await au.automation(
        "user_made", basic(steps=[{"id": "x", "action": "test.admin_only"}]), author="ursula"
    )
    await au.emit({"value": 1})
    [execution] = await au.executions(authored_by_user)
    assert (
        execution.status == "refused" and execution.error_code == "action_forbidden" and au.record.calls == []
    )
    automation, _ = await au.module.definitions.get(authored_by_user)
    assert automation.needs_review
    by_boss = await au.automation("boss_made", basic(steps=[{"id": "x", "action": "test.admin_only"}]))
    await au.emit({"value": 2})
    assert (await au.executions(by_boss))[-1].status == "success"
    await set_state(module_of(app), au.people["boss"], AccountState.SUSPENDED)  # the author loses access
    await au.emit({"value": 3})
    assert (await au.executions(by_boss))[-1].status == "refused"


async def test_system_identity_scopes(au: AutoHarness) -> None:
    definition = basic(identity={"kind": "system", "scopes": ["users.self.manage"]})
    automation = await au.automation("system", definition)
    await au.emit({"value": 1})
    assert (await au.executions(automation))[-1].status == "success"
    with pytest.raises(ValidationFailed) as raised:
        au.module.definitions.validate(basic(identity={"kind": "system", "scopes": ["audit.read"]}))
    assert any("needs users.self.manage" in e for e in raised.value.extensions["errors"])
    wide = await au.module.definitions.create(
        au.p("ursula"),
        "wide",
        basic(identity={"kind": "system", "scopes": ["users.self.manage", "users.manage"]}),
    )
    with pytest.raises(Forbidden):
        await au.module.definitions.publish(au.p("ursula"), wide.id)


async def test_permission_condition_never_grants(au: AutoHarness) -> None:
    au.actions.register(ActionType("test.admin_only", "x", "users.manage", "x", au.record, "module:test"))
    automation = await au.automation(
        "check",
        basic(
            conditions={"leaf": "permission_held", "params": {"permission": "users.self.manage"}},
            steps=[{"id": "x", "action": "test.admin_only"}],
        ),
        author="ursula",
    )
    await au.emit({"value": 1})
    [execution] = await au.executions(automation)
    assert execution.conditions_trace == [{"leaf": "permission_held", "result": True}]
    assert execution.status == "refused"  # holding the condition's permission grants nothing
