"""027 T021 — every XP/Coins ledger write queues exactly one ``progression.changed`` live notification for the
owner only, with post-transaction values; ``level_up`` is true only when a level is crossed; a rolled-back
write (overdraft) queues nothing; contribution writes queue nothing."""

import pytest
from sqlalchemy import text

from portalab.capabilities.economy import InsufficientCoins
from tests.integration.gamification.conftest import GamHarness

pytestmark = pytest.mark.integration


async def _live(gm: GamHarness) -> list[tuple[str | None, dict[str, object]]]:
    async with gm.database.session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT audience_user_id::text, payload FROM core.live_event "
                    "WHERE topic = 'progression.changed' ORDER BY seq"
                )
            )
        ).all()
    return [(r[0], r[1]) for r in rows]


async def test_progression_changes_are_pushed_to_the_owner(gm: GamHarness) -> None:
    user, other = gm.people["ursula"], gm.people["ulrich"]
    await gm.module.rewards.grant_manual(gm.p("boss"), user, "xp", 50, reason="seed", idempotency_key="a")
    await gm.module.rewards.grant_manual(gm.p("boss"), user, "xp", 60, reason="seed", idempotency_key="b")
    await gm.module.rewards.grant_manual(gm.p("boss"), user, "coins", 30, reason="seed", idempotency_key="c")
    await gm.module.rewards.grant_manual(gm.p("boss"), user, "xp", 60, reason="seed", idempotency_key="b")
    live = await _live(gm)
    assert [audience for audience, _ in live] == [str(user)] * 3  # the duplicate grant pushes nothing
    first, second, third = (payload for _, payload in live)
    assert first["xp"] == 50 and first["level_up"] is False and first["delta_xp"] == 50
    assert second["xp"] == 110 and second["level"] == 2 and second["level_up"] is True
    assert second["level_floor"] == 100 and second["next_level_at"] is not None
    assert third["coins"] == 30 and third["delta_coins"] == 30 and third["xp"] == 110
    assert third["level_up"] is False
    assert str(other) not in {audience for audience, _ in live}

    with pytest.raises(InsufficientCoins):
        await gm.module.economy.spend(
            user, 999, reason="too much", source_kind="marketplace", source_ref="x", idempotency_key="s1"
        )
    assert len(await _live(gm)) == 3  # rolled back with the transaction

    await gm.module.rewards.grant_contribution(user, "help", "ref-1", gm.p("boss"))
    assert len(await _live(gm)) == 3  # contribution is not shown in the header
