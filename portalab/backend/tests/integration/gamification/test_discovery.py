"""027 — discovery missions: a new member's first steps, each rewarded once — created on a fresh portal
(never again once their key was used), counted on the member's own doing (the starter dashboard does not
count as arranging it), and done once only."""

from datetime import timedelta

import pytest
from sqlalchemy import text

from portalab.core.errors import ValidationFailed
from portalab.modules.gamification.quests.discovery import DISCOVERY
from tests.integration.gamification.conftest import SYSTEM, GamHarness

pytestmark = pytest.mark.integration


async def test_missions_exist_once_and_reward_once(gm: GamHarness) -> None:
    assert await gm.module.quests.ensure_discovery() == len(DISCOVERY)
    assert await gm.module.quests.ensure_discovery() == 0  # never twice
    await gm.module.quests.retire(SYSTEM, "discover_shop")
    assert await gm.module.quests.ensure_discovery() == 0  # a retired mission is not brought back
    gm.clock.advance(timedelta(minutes=1))
    user = gm.people["ursula"]

    async def emit(event_type: str, payload: dict[str, object]) -> None:
        await gm.module.pipeline.process(gm.envelope(user, payload, event_type=event_type))

    step = "user.onboarding_step_completed"
    await emit(step, {"step": "profile"})  # another step
    await emit(step, {"step": "tour"})
    await emit(step, {"step": "tour"})  # done once only
    layout = {"layout_version": 1, "widgets": 9, "active": 9}
    await emit("dashboard.layout_changed", {**layout, "starter": True})  # the starter: not mine
    async with gm.database.session() as session:
        done = (
            (
                await session.execute(
                    text(
                        "SELECT payload->>'quest' FROM events.events "
                        "WHERE type = 'quest.completed' ORDER BY seq"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert done == ["discover_tour"]
    assert await gm.balance(user, "xp") == 25 and await gm.balance(user, "coins") == 10
    await emit("dashboard.layout_changed", {**layout, "starter": False})
    mine = {q["key"]: q for q in await gm.module.quests.mine(user, kinds=["discovery"])}
    assert mine["discover_dashboard"]["completed_at"] and not mine["discover_profile"]["completed_at"]
    assert "discover_shop" not in mine


async def test_a_mission_is_done_once(gm: GamHarness) -> None:
    raw = {**DISCOVERY["discover_profile"], "period": "week"}
    with pytest.raises(ValidationFailed):
        await gm.module.quests.save(SYSTEM, "weekly_profile", raw)
