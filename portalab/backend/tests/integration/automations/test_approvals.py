"""019 T014 — sensitive actions: a destructive action waits per execution (``awaiting_approval``); approve
runs it once (params hash bound); reject or expiry never execute; a sensitive non-destructive action with
a standing approval attested at publish runs directly; approvers need ``automation.approve``; audited."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.capabilities.automation_actions import ActionType
from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict, Forbidden
from tests.integration.automations.conftest import AutoHarness, Recorder, basic
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_destructive_per_run(au: AutoHarness, client: AsyncClient) -> None:
    wipe = Recorder()
    au.actions.register(
        ActionType(
            "test.wipe",
            "wipe",
            "users.manage",
            "x",
            wipe,
            "module:test",
            {"text": "string?"},
            sensitivity="destructive",
        )
    )
    automation = await au.automation(
        "wiper",
        basic(
            steps=[
                {"id": "before", "action": "test.record"},
                {"id": "wipe", "action": "test.wipe", "params": {"text": "${event.label}"}},
                {"id": "after", "action": "test.record", "params": {"text": "done ${steps.wipe.recorded}"}},
            ]
        ),
    )
    await au.emit({"value": 1, "label": "everything"})
    [execution] = await au.executions(automation)
    assert execution.status == "awaiting_approval" and wipe.calls == [] and len(au.record.calls) == 1
    await login(client, "ursula")
    assert (await client.get("/api/v1/admin/automations/approvals")).status_code == 403
    await login(client, "boss")
    [pending] = (await client.get("/api/v1/admin/automations/approvals")).json()
    assert pending["action"] == "test.wipe" and "everything" in pending["summary"]
    approved = await client.post(f"/api/v1/admin/automations/approvals/{pending['id']}/approve")
    assert approved.json() == {"status": "success", "error": None}
    assert len(wipe.calls) == 1 and au.record.calls[-1]["params"] == {"text": "done 1"}
    again = await client.post(f"/api/v1/admin/automations/approvals/{pending['id']}/approve")
    assert again.status_code == 409 and len(wipe.calls) == 1
    with pytest.raises(Forbidden):
        await au.module.approvals.approve(
            Principal(channel="ai", acting_for=au.people["boss"]), pending["id"]
        )
    await au.emit({"value": 2, "label": "more"})
    second = (await au.module.approvals.queue())[0]
    await au.module.approvals.reject(au.p("boss"), second.id)
    await au.emit({"value": 3, "label": "late"})
    third = (await au.module.approvals.queue())[0]
    async with au.database.unit_of_work() as uow:
        await uow.session.execute(
            text(
                "UPDATE automations.approvals SET params = "
                "jsonb_set(params, '{approved_params,text}', '\"tampered\"') WHERE id = :i"
            ),
            {"i": third.id},
        )
    with pytest.raises(Conflict):
        await au.module.approvals.approve(au.p("boss"), third.id)
    au.clock.advance(timedelta(hours=73))
    assert await au.module.approvals.expire() == 1
    statuses = [(e.status, e.error_code) for e in await au.executions(automation)]
    assert statuses == [("success", None), ("refused", "approval_rejected"), ("refused", "approval_expired")]
    assert len(wipe.calls) == 1
    async with au.database.session() as session:
        audits = (
            (
                await session.execute(
                    text("SELECT action FROM audit.audit_entries WHERE action LIKE 'automation.approval_%'")
                )
            )
            .scalars()
            .all()
        )
    assert sorted(audits) == ["automation.approval_approved", "automation.approval_rejected"]


async def test_standing_approval_for_sensitive(au: AutoHarness, client: AsyncClient) -> None:
    grant = Recorder()
    au.actions.register(
        ActionType(
            "test.grant", "grant", "users.self.manage", "x", grant, "module:test", sensitivity="sensitive"
        )
    )
    row = await au.module.definitions.create(
        au.p("boss"), "granter", basic(steps=[{"id": "g", "action": "test.grant"}])
    )
    await login(client, "boss")
    first = await client.post(f"/api/v1/admin/automations/{row.id}/publish", json={})
    assert first.status_code == 409 and first.json()["code"] == "authz.confirmation_required"
    published = await client.post(
        f"/api/v1/admin/automations/{row.id}/publish", json={"confirmation": first.json()["confirmation"]}
    )
    assert published.status_code == 200
    detail = (await client.get(f"/api/v1/admin/automations/{row.id}")).json()
    assert detail["versions"][-1]["standing_approvals"] == ["test.grant"]
    await au.emit({"value": 1})
    assert (await au.executions(row.id))[-1].status == "success" and len(grant.calls) == 1
