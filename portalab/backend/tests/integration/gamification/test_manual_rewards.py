"""013 T013 — manual rewards need ``rewards.grant`` and a reason, are marked manual with the actor, audited,
and need a confirmation at or above the threshold; AI/automation callers are bounded by the acting principal;
rule publish/retire are audited and sensitive."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.core.authz_port import Principal
from portalab.core.errors import Forbidden
from tests.integration.gamification.conftest import GamHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_manual_grant_api(gm: GamHarness, client: AsyncClient) -> None:
    user = gm.people["ursula"]
    await login(client, "ursula")
    body = {"user_id": str(user), "value": "coins", "amount": 50, "reason": "Helped a newcomer"}
    assert (await client.post("/api/v1/admin/gamification/manual-grants", json=body)).status_code == 403
    await login(client, "boss")
    assert (
        await client.post("/api/v1/admin/gamification/manual-grants", json={**body, "reason": ""})
    ).status_code == 422
    done = await client.post("/api/v1/admin/gamification/manual-grants", json=body)
    assert done.status_code == 200, done.text
    assert (
        done.json()["transaction"]["kind"] == "manual"
        and done.json()["transaction"]["reason"] == "Helped a newcomer"
    )
    big = {**body, "amount": 5000}
    first = await client.post("/api/v1/admin/gamification/manual-grants", json=big)
    assert first.status_code == 409 and first.json()["code"] == "authz.confirmation_required"
    token = first.json()["confirmation"]
    tampered = await client.post(
        "/api/v1/admin/gamification/manual-grants", json={**big, "amount": 6000, "confirmation": token}
    )
    assert tampered.status_code == 403
    again = await client.post("/api/v1/admin/gamification/manual-grants", json=big)
    confirmed = await client.post(
        "/api/v1/admin/gamification/manual-grants", json={**big, "confirmation": again.json()["confirmation"]}
    )
    assert confirmed.status_code == 200
    assert await gm.balance(user, "coins") == 5050
    async with gm.database.session() as session:
        rows = (
            await session.execute(text("SELECT actor_user_id, source_kind FROM gamification.transactions"))
        ).all()
        audits = (
            (
                await session.execute(
                    text("SELECT action FROM audit.audit_entries WHERE action = 'economy.manual_grant'")
                )
            )
            .scalars()
            .all()
        )
    assert {(r.actor_user_id, r.source_kind) for r in rows} == {(gm.people["boss"], "manual")}
    assert len(audits) == 2


async def test_bounded_callers(gm: GamHarness) -> None:
    user = gm.people["ursula"]
    ai_for_plain_user = Principal(channel="ai", acting_for=gm.people["ulrich"])
    with pytest.raises(Forbidden):
        await gm.module.rewards.grant_manual(
            ai_for_plain_user, user, "xp", 10, reason="please", idempotency_key="x"
        )
    ai_for_admin = Principal(channel="automation", acting_for=gm.people["boss"])
    granted = await gm.module.rewards.grant_manual(
        ai_for_admin, user, "xp", 10, reason="automation", idempotency_key="y"
    )
    assert granted is not None and granted.delta == 10


async def test_rule_admin_is_audited(gm: GamHarness, client: AsyncClient) -> None:
    await login(client, "boss")
    definition = {"event_type": "media.played", "grants": [{"value": "xp", "amount": 5}]}
    saved = await client.post("/api/v1/admin/gamification/rules/listen", json={"definition": definition})
    assert saved.status_code == 201 and saved.json()["status"] == "draft"
    bad = await client.post(
        "/api/v1/admin/gamification/rules/listen", json={"definition": {"event_type": "media.played"}}
    )
    assert bad.status_code == 422 and bad.json()["code"] == "economy.rule_invalid"
    simulated = await client.post(
        "/api/v1/admin/gamification/rules/listen/simulate",
        json={"samples": [{"payload": {"minutes": 3, "genre": "x"}}]},
    )
    assert simulated.json()[0]["grants"][0]["amount"] == 5
    published = await client.post("/api/v1/admin/gamification/rules/listen/publish", json={"version": 1})
    assert published.json()["status"] == "active" and published.json()["effective_from"]
    assert (
        await client.post("/api/v1/admin/gamification/rules/listen/publish", json={"version": 1})
    ).status_code == 409
    assert (await client.post("/api/v1/admin/gamification/rules/listen/retire")).json()["status"] == "retired"
    async with gm.database.session() as session:
        actions = (
            (
                await session.execute(
                    text(
                        "SELECT action FROM audit.audit_entries "
                        "WHERE action LIKE 'economy.rule_%' ORDER BY seq"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert actions == ["economy.rule_saved", "economy.rule_published", "economy.rule_retired"]
