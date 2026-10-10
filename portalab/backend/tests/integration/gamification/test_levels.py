"""013 T023 — crossing a threshold emits one ``user.level_up`` (dedup per user and level); the level is
never a spendable balance; rebuilding from the ledger gives the same level; values are shown separately."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.modules.gamification.levels.curve import Curve
from tests.integration.gamification.conftest import GamHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_level_ups(gm: GamHarness, client: AsyncClient) -> None:
    user = gm.people["ursula"]
    for index, amount in enumerate((50, 60, 500, 10)):
        await gm.module.rewards.grant_manual(
            gm.p("boss"), user, "xp", amount, reason="seed", idempotency_key=f"l{index}"
        )
    async with gm.database.session() as session:
        levels = (
            (
                await session.execute(
                    text(
                        "SELECT payload->>'level' FROM events.events "
                        "WHERE type = 'user.level_up' ORDER BY seq"
                    )
                )
            )
            .scalars()
            .all()
        )
        total = await session.scalar(
            text("SELECT sum(delta) FROM gamification.transactions WHERE user_id = :u AND value = 'xp'"),
            {"u": user},
        )
        values = (
            (await session.execute(text("SELECT DISTINCT value FROM gamification.transactions")))
            .scalars()
            .all()
        )
    assert levels == ["2", "4"]  # 110 XP → level 2; 610 XP → level 4 (one event for the jump)
    assert Curve(1).level_for(int(total)) == 4 and set(values) == {"xp"}
    await login(client, "ursula")
    progression = (await client.get("/api/v1/me/progression")).json()
    assert progression == {
        "user_id": str(user),
        "xp": 620,
        "level": 4,
        "level_floor": 520,
        "next_level_at": 800,
        "contribution": 0,
        "coins": 0,
        "reserved_coins": 0,
        "achievements": 0,
        "boost": None,  # #55: none bought
    }
