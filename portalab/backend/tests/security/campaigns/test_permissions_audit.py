"""014 T029 — only ``campaigns.manage`` mutates; sensitive actions are audited (actor, action, context,
result) and confirmed; hostile definitions are rejected; events carry no secrets or personal data."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.campaigns.conftest import HALLOWEEN, CampHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_permissions_and_audit(cm: CampHarness, client: AsyncClient) -> None:
    await login(client, "ursula")
    body = {"key": "halloween", "definition": HALLOWEEN}
    assert (await client.post("/api/v1/admin/campaigns", json=body)).status_code == 403
    assert (await client.get("/api/v1/campaigns/active")).status_code == 200
    await login(client, "boss")
    created = await client.post("/api/v1/admin/campaigns", json=body)
    assert created.status_code == 201, created.text
    campaign = created.json()["id"]
    hostile = {**HALLOWEEN, "names": {"en": "x" * 5000}}
    assert (await client.post("/api/v1/admin/campaigns", json={"key": "evil", "definition": hostile})).json()[
        "code"
    ] == "campaign.invalid_definition"
    unconfirmed = await client.post(
        f"/api/v1/admin/campaigns/{campaign}/cancel", json={"reason": "Wrong dates"}
    )
    assert unconfirmed.status_code == 409
    cancelled = await client.post(
        f"/api/v1/admin/campaigns/{campaign}/cancel",
        json={"reason": "Wrong dates", "confirmation": unconfirmed.json()["confirmation"]},
    )
    assert cancelled.json()["state"] == "ended"
    assert (await client.post(f"/api/v1/admin/campaigns/{campaign}/archive")).json()["state"] == "archived"
    announce = await client.post(f"/api/v1/admin/campaigns/{campaign}/announce", json={"message": "Boo"})
    assert announce.status_code in (
        200,
        503,
    )  # broadcast permission held by the Admin; 503 without notifications
    async with cm.database.session() as session:
        audits = (
            await session.execute(
                text(
                    "SELECT action, actor_user_id, result FROM audit.audit_entries "
                    "WHERE action LIKE 'campaign.%' ORDER BY seq"
                )
            )
        ).all()
        payloads = (
            (
                await session.execute(
                    text("SELECT payload::text FROM events.events WHERE type LIKE 'campaign.%'")
                )
            )
            .scalars()
            .all()
        )
    assert [a.action for a in audits] == ["campaign.created", "campaign.cancelled", "campaign.archived"]
    assert all(a.actor_user_id == cm.people["boss"] and a.result == "success" for a in audits)
    assert all("boss" not in p and str(cm.people["boss"]) not in p for p in payloads)
