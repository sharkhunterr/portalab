"""015 T015 — only ``projects.manage`` moves projects; funders see their own fundings, everyone sees public
aggregates, nobody else sees who funded; the per-funder list is Admin-only; transitions are audited; event
payloads carry ids and amounts only."""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import RULES, MkHarness

pytestmark = pytest.mark.integration


async def test_authz_and_privacy(mk: MkHarness, client: AsyncClient) -> None:
    project = await mk.project(open_with=RULES)
    await mk.coins("ursula", 100)
    await mk.module.fundings.fund(mk.p("ursula"), project, 60, acknowledged=True, request_key="a")
    await login(client, "ulrich")
    for path, body in (
        (f"/api/v1/admin/projects/{project}/transition", {"to": "validation"}),
        (f"/api/v1/admin/projects/{project}/abandon", {}),
        (f"/api/v1/admin/projects/{project}/reject", {}),
        (f"/api/v1/admin/projects/{project}/validate", {"approve": True}),
    ):
        assert (await client.post(path, json=body)).status_code == 403
    assert (await client.get(f"/api/v1/admin/projects/{project}/fundings")).status_code == 403
    assert (await client.get("/api/v1/me/fundings")).json() == []  # not ursula's
    public = await client.get(f"/api/v1/projects/{project}")
    assert public.json()["totals"] == {"reserved": 60, "consumed": 0, "funders": 1, "goal_amount": None}
    assert str(mk.people["ursula"]) not in public.text
    await login(client, "boss")
    listed = (await client.get(f"/api/v1/admin/projects/{project}/fundings")).json()
    assert [(f["user_id"], f["amount"]) for f in listed] == [(str(mk.people["ursula"]), 60)]

    async with mk.database.session() as session:
        payloads = (
            (
                await session.execute(
                    text("SELECT payload::text FROM events.events WHERE type LIKE 'project.%'")
                )
            )
            .scalars()
            .all()
        )
        audits = await session.scalar(
            text("SELECT count(*) FROM audit.audit_entries WHERE action = 'project.transitioned'")
        )
    assert audits == 2  # promote and open
    assert all("ursula" not in p for p in payloads)
    for payload in map(json.loads, payloads):
        assert set(payload) <= {"project", "proposal", "from_state", "to_state", "seq", "funding", "amount"}
