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


async def test_a_mission_is_done_by_its_tour_or_by_doing_it(gm: GamHarness) -> None:
    """Issue 121: following a mission's guided tour to its end completes it (and rewards it) as doing the
    thing does — whichever comes first, once."""
    await gm.module.quests.ensure_discovery()
    gm.clock.advance(timedelta(minutes=1))
    user = gm.people["ursula"]

    async def emit(event_type: str, payload: dict[str, object]) -> None:
        await gm.module.pipeline.process(gm.envelope(user, payload, event_type=event_type))

    await emit("user.tour_completed", {"tour": "media"})  # a tour without a mission
    await emit("user.tour_completed", {"tour": "profile"})
    await emit("user.profile_updated", {})  # done already: nothing more
    await emit("user.tour_completed", {"tour": "shop"})
    mine = {q["key"]: q for q in await gm.module.quests.mine(user, kinds=["discovery"])}
    done = {key for key, quest in mine.items() if quest["completed_at"]}
    assert done == {"discover_profile", "discover_shop"}
    assert await gm.balance(user, "xp") == 25 + 30 and await gm.balance(user, "coins") == 10


async def test_a_mission_as_shipped_before_is_brought_up_to_date(gm: GamHarness) -> None:
    """Issue 121: the missions an earlier release created are updated at start — unless an administrator
    changed them since."""
    from portalab.modules.gamification.quests.discovery import SUPERSEDED

    await gm.module.quests.save(SYSTEM, "discover_profile", SUPERSEDED["discover_profile"][0])
    mine = {**SUPERSEDED["discover_dashboard"][0], "label": "Make the dashboard yours"}
    await gm.module.quests.save(SYSTEM, "discover_dashboard", mine)  # an administrator's own wording
    assert await gm.module.quests.ensure_discovery() == len(DISCOVERY) - 1
    assert await gm.module.quests.ensure_discovery() == 0
    async with gm.database.session() as session:
        latest = dict(
            (
                await session.execute(
                    text(
                        "SELECT DISTINCT ON (key) key, definition->>'complete_on' FROM gamification.quests "
                        "WHERE key IN ('discover_profile', 'discover_dashboard') ORDER BY key, version DESC"
                    )
                )
            ).all()
        )
    assert latest == {"discover_profile": "any", "discover_dashboard": "all"}  # the admin's kept


async def test_a_mission_gains_its_french_texts(gm: GamHarness) -> None:
    """#307: a mission as the previous release shipped it (English only) gains its French texts at start;
    a member reads them through ``translations``, with when a periodic objective starts again."""
    from portalab.modules.gamification.quests.discovery import SUPERSEDED

    await gm.module.quests.save(SYSTEM, "discover_tour", SUPERSEDED["discover_tour"][-1])
    await gm.module.quests.ensure_discovery()
    await gm.module.quests.save(
        SYSTEM,
        "daily_visit",
        {
            "kind": "daily",
            "label": "Daily visit",
            "period": "day",
            "steps": [{"kind": "event_count", "event_type": "user.signed_in", "count": 1}],
            "translations": {"fr": {"label": "Visite du jour"}},
        },
    )
    gm.clock.advance(timedelta(minutes=1))
    mine = {q["key"]: q for q in await gm.module.quests.mine(gm.people["ursula"])}
    assert mine["discover_tour"]["translations"]["fr"]["label"] == "Faites le tour"
    assert mine["discover_tour"]["complete_on"] == "any"
    assert mine["discover_tour"]["resets_at"] is None
    assert mine["daily_visit"]["translations"] == {"fr": {"label": "Visite du jour", "description": ""}}
    assert mine["daily_visit"]["resets_at"] is not None
