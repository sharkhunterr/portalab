"""#62 — my progression over time: XP, Coins and Contribution gained per day, and the moments a level was
reached (a jump over several levels gives one moment per level)."""

import pytest
from httpx import AsyncClient

from tests.integration.gamification.conftest import RULE, GamHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_timeline_and_level_ups(gm: GamHarness, client: AsyncClient) -> None:
    await gm.rule("played", RULE)
    user = gm.people["ursula"]
    curve = await gm.module.levels.curve()
    await gm.emit(user)  # 20 XP and 5 Coins
    await gm.module.rewards.grant_manual(
        gm.p("boss"), user, "xp", curve.threshold(3), reason="seed", idempotency_key="t1"
    )
    await gm.module.rewards.grant_manual(
        gm.p("boss"), user, "contribution", 7, reason="seed", idempotency_key="t2"
    )
    await login(client, "ursula")
    body = (await client.get("/api/v1/me/progression/timeline?days=7")).json()
    assert body["start_level"] == 1
    assert [u["level"] for u in body["level_ups"]] == [2, 3]  # one movement, two levels
    assert body["level_ups"][0]["at"] == body["level_ups"][1]["at"]
    totals = {k: sum(d[k] for d in body["days"]) for k in ("xp", "coins", "contribution")}
    assert totals == {"xp": 20 + curve.threshold(3), "coins": 5, "contribution": 7}


async def test_a_correction_dated_with_its_grant_cancels_it(gm: GamHarness, client: AsyncClient) -> None:
    from sqlalchemy import select

    from portalab.modules.gamification.ledger.writer import Entry
    from portalab.modules.gamification.models import LedgerTransaction

    user = gm.people["ursula"]
    curve = await gm.module.levels.curve()
    granted = await gm.module.rewards.grant_manual(
        gm.p("boss"), user, "xp", curve.threshold(40), reason="test", idempotency_key="big"
    )
    assert granted is not None
    async with gm.module.database.unit_of_work() as uow:
        grant = await uow.session.scalar(select(LedgerTransaction).where(LedgerTransaction.id == granted.id))
        assert grant is not None
        await gm.module.writer.record(
            uow.session,
            Entry(
                user_id=user,
                value="xp",
                delta=-(curve.threshold(40) - curve.threshold(3)),
                kind="correction",
                source_kind="manual",
                idempotency_key="big-correction",
                occurred_at=grant.occurred_at,
                reason="test grant taken back",
                reverses_transaction_id=grant.id,
            ),
        )
    assert (await gm.module.progression.progress(user)).level == 3
    await login(client, "ursula")
    body = (await client.get("/api/v1/me/progression/timeline?days=7")).json()
    assert [u["level"] for u in body["level_ups"]] == [2, 3]  # never 40: the grant and its correction net
    assert sum(d["xp"] for d in body["days"]) == curve.threshold(3)
    sources = (await client.get("/api/v1/me/progression/sources?value=xp&days=7")).json()
    assert sources["total"] == curve.threshold(3)
