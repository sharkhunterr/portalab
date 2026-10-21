"""013 T021 — beyond the thresholds rewards are withheld and flagged (``economy.anomaly_flagged``); approve
records them, reject drops them with a reason, confirm-abuse also reverses the window's rule grants by
corrections (never edits); every decision audited; nothing dropped silently."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.gamification.conftest import GamHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def burst(gm: GamHarness, count: int) -> None:
    for i in range(count):
        await gm.module.pipeline.process(
            gm.envelope(gm.people["ursula"], at=gm.clock.now() + timedelta(seconds=i + 1))
        )


async def setup(gm: GamHarness) -> None:
    from dataclasses import replace

    gm.module.config = replace(gm.module.config, anomaly_max_grants_per_hour=3)
    await gm.rule("listen", {"event_type": "media.played", "grants": [{"value": "xp", "amount": 10}]})


async def test_withhold_then_approve(gm: GamHarness, client: AsyncClient) -> None:
    await setup(gm)
    await burst(gm, 5)
    user = gm.people["ursula"]
    assert await gm.balance(user) == 30
    await login(client, "boss")
    queue = (await client.get("/api/v1/admin/economy/anomalies")).json()
    assert len(queue) == 1 and queue[0]["kind"] == "grants_per_hour" and len(queue[0]["withheld"]) == 2
    # one member's flags only (their admin card)
    mine = (await client.get("/api/v1/admin/economy/anomalies", params={"user_id": str(user)})).json()
    others = await client.get("/api/v1/admin/economy/anomalies", params={"user_id": str(gm.people["boss"])})
    assert [f["id"] for f in mine] == [queue[0]["id"]] and others.json() == []
    approved = await client.post(
        f"/api/v1/admin/economy/anomalies/{queue[0]['id']}/approve", json={"reason": "Legit marathon"}
    )
    assert len(approved.json()["transactions"]) == 2 and await gm.balance(user) == 50
    again = await client.post(
        f"/api/v1/admin/economy/anomalies/{queue[0]['id']}/approve", json={"reason": "twice"}
    )
    assert again.status_code == 409
    async with gm.database.session() as session:
        flagged = await session.scalar(
            text("SELECT count(*) FROM events.events WHERE type = 'economy.anomaly_flagged'")
        )
        audits = await session.scalar(
            text("SELECT count(*) FROM audit.audit_entries WHERE action = 'economy.anomaly_approved'")
        )
    assert flagged == 1 and audits == 1


async def test_reject_and_confirm_abuse(gm: GamHarness, client: AsyncClient) -> None:
    await setup(gm)
    await burst(gm, 4)
    user = gm.people["ursula"]
    await login(client, "boss")
    flag = (await client.get("/api/v1/admin/economy/anomalies")).json()[0]
    assert (
        await client.post(f"/api/v1/admin/economy/anomalies/{flag['id']}/reject", json={"reason": "Bot"})
    ).json() == {"dropped": 1}
    gm.clock.advance(timedelta(hours=2))
    await burst(gm, 4)
    assert await gm.balance(user) == 60
    flag = (await client.get("/api/v1/admin/economy/anomalies")).json()[0]
    confirmed = await client.post(
        f"/api/v1/admin/economy/anomalies/{flag['id']}/confirm-abuse", json={"reason": "Script"}
    )
    assert len(confirmed.json()["corrections"]) == 3 and await gm.balance(user) == 30
    async with gm.database.session() as session:
        statuses = (
            (await session.execute(text("SELECT status FROM gamification.withheld ORDER BY occurred_at")))
            .scalars()
            .all()
        )
        corrections = (
            await session.execute(
                text(
                    "SELECT count(*) FROM gamification.transactions "
                    "WHERE kind = 'correction' AND reverses_transaction_id IS NOT NULL"
                )
            )
        ).scalar()
    assert statuses == ["rejected", "rejected"] and corrections == 3
    assert (await client.get("/api/v1/admin/economy/anomalies", params={"status": "confirmed"})).json()[0][
        "status"
    ] == "confirmed"
    await login(client, "ursula")
    assert (await client.get("/api/v1/admin/economy/anomalies")).status_code == 403
