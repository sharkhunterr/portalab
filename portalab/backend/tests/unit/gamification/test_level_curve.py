"""013 T006 — level curve: monotonic thresholds, boundaries, multi-level jumps; a new curve version
recomputes cached levels without emitting level-ups."""

import itertools

import pytest

from portalab.modules.gamification.levels.curve import Curve


def test_thresholds_and_boundaries() -> None:
    curve = Curve(1)
    thresholds = [curve.threshold(n) for n in range(1, 30)]
    assert thresholds[:4] == [0, 100, 283, 520]
    assert all(a < b for a, b in itertools.pairwise(thresholds))
    assert curve.level_for(0) == 1 and curve.level_for(99) == 1 and curve.level_for(100) == 2
    assert curve.level_for(519) == 3 and curve.level_for(520) == 4
    assert curve.level_for(10_000) == 22  # one big grant jumps several levels
    assert curve.next_threshold(150) == 283


@pytest.mark.integration
async def test_curve_change_recomputes_silently(gm) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    user = gm.people["ursula"]
    await gm.module.rewards.grant_manual(gm.p("boss"), user, "xp", 300, reason="seed", idempotency_key="seed")
    assert await gm.module.levels.level_of(user) == 3
    await gm.module.levels.publish({"kind": "power", "base": 50, "exponent": 1.0})
    assert await gm.module.levels.level_of(user) == 7
    async with gm.database.session() as session:
        level = await session.scalar(
            text("SELECT level FROM gamification.balances WHERE user_id = :u AND value = 'xp'"), {"u": user}
        )
        ups = await session.scalar(text("SELECT count(*) FROM events.events WHERE type = 'user.level_up'"))
    assert level == 7 and ups == 1  # only the original crossing (1 → 3)
