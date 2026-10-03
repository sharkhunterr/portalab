"""019 T026 — ≥ N consecutive failures suspend the automation with a reason, an event and a notification;
executions while suspended are recorded; re-enable resets the counters; history keeps references (trigger
ref, condition trace, step outcomes) — no payload bodies; retention purges old executions; a failing
automation never affects the others."""

from datetime import timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.capabilities.automation_actions import ActionType
from portalab.capabilities.notifications import NOTIFY, CommunicationRef, CommunicationRequest
from portalab.core.authz_port import Principal
from tests.integration.automations.conftest import AutoHarness, Recorder, basic
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


class Outbox:
    def __init__(self) -> None:
        self.sent: list[CommunicationRequest] = []

    async def send(
        self, request: CommunicationRequest, *, caller: Principal | None = None
    ) -> CommunicationRef:
        self.sent.append(request)
        return CommunicationRef(uuid4(), True, 1)


async def test_suspension_and_history(au: AutoHarness, client: AsyncClient) -> None:
    outbox = Outbox()
    au.ev.full.identity.capabilities.provide(NOTIFY, outbox, instance_ref="t", owner="test")
    broken = Recorder(fail=True)
    au.actions.register(ActionType("test.broken", "broken", "users.self.manage", "x", broken, "module:test"))
    failing = await au.automation(
        "failing", basic(conditions=None, steps=[{"id": "b", "action": "test.broken"}])
    )
    healthy = await au.automation("healthy", basic(conditions=None))
    for index in range(7):
        await au.emit({"value": index, "label": f"secret body {index}"})
    statuses = [e.status for e in await au.executions(failing)]
    assert statuses == ["failed"] * 5 + ["suspended"] * 2
    assert [e.status for e in await au.executions(healthy)] == ["success"] * 7
    await login(client, "boss")
    detail = (await client.get(f"/api/v1/admin/automations/{failing}")).json()
    assert detail["state"] == "suspended" and "5 consecutive failures" in detail["suspend_reason"]
    assert [r.category for r in outbox.sent] == ["automations.suspended"]
    executions = (await client.get(f"/api/v1/admin/automations/{failing}/executions")).json()
    assert executions[0]["status"] == "suspended" and "secret body" not in str(executions)
    one = (await client.get(f"/api/v1/admin/automations/executions/{executions[-1]['id']}")).json()
    assert one["steps"][0]["error_code"] == "RuntimeError" and one["trigger_ref"]["type"] == "test.happened"
    reenabled = await client.post(f"/api/v1/admin/automations/{failing}/reenable")
    assert reenabled.json()["state"] == "active" and reenabled.json()["consecutive_failures"] == 0
    broken.fail = False
    await au.emit({"value": 1})
    assert (await au.executions(failing))[-1].status == "success"
    au.clock.advance(timedelta(days=91))
    assert await au.module.history.purge(90) >= 15
    async with au.database.session() as session:
        assert await session.scalar(text("SELECT count(*) FROM automations.executions")) == 0
        suspended = await session.scalar(
            text("SELECT count(*) FROM events.events WHERE type = 'automation.suspended'")
        )
    assert suspended == 1
