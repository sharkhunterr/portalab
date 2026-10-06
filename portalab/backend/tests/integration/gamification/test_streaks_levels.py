"""027 — play streaks multiply the rewards of counted events by the highest tier reached (a missed day
starts over); level rewards give Coins/Contribution once per tier reached; the tuning endpoints."""

from dataclasses import replace
from datetime import timedelta

import pytest
from httpx import AsyncClient

from portalab.modules.gamification.streaks.service import multiplier_for, parse_streak
from tests.integration.gamification.conftest import RULE, GamHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration

STREAK = {
    "enabled": True,
    "event_types": ["media.played"],
    "values": ["xp"],
    "tiers": [{"days": 2, "multiplier": 1.5}, {"days": 5, "multiplier": 2.0}],
}


def test_multiplier_for() -> None:
    config = parse_streak(STREAK)
    assert [multiplier_for(config, n) for n in (0, 1, 2, 4, 5, 9)] == [1.0, 1.0, 1.5, 1.5, 2.0, 2.0]
    assert parse_streak({"tiers": [{"days": 0, "multiplier": 2}]}).enabled is False  # invalid → off


async def test_streak_multiplies(gm: GamHarness) -> None:
    gm.module.config = replace(gm.module.config, streak=STREAK)
    await gm.rule("played", RULE)
    user = gm.people["ursula"]
    start = gm.clock.now() + timedelta(hours=1)
    for day in (0, 1, 2, 3, 4):
        await gm.emit(user, at=start + timedelta(days=day))
    # 20 · (1, 1.5, 1.5, 1.5, 2) — coins are not counted values
    assert await gm.balance(user) == 20 + 30 + 30 + 30 + 40
    assert await gm.balance(user, "coins") == 25
    await gm.emit(user, at=start + timedelta(days=7))  # two missed days: the streak starts over
    assert await gm.balance(user) == 150 + 20
    state = await gm.module.streaks.current(user, start + timedelta(days=7))
    assert state["days"] == 1 and state["next"] == {"days": 2, "multiplier": 1.5}


async def test_pace_multiplies_every_rule(gm: GamHarness, client: AsyncClient) -> None:
    await gm.rule("played", RULE)
    await login(client, "boss")
    saved = await client.put("/api/v1/admin/gamification/pace", json={"factor": 1.5, "values": ["xp"]})
    assert saved.status_code == 200, saved.text
    user = gm.people["ursula"]
    await gm.emit(user)
    assert await gm.balance(user) == 30 and await gm.balance(user, "coins") == 5
    population = (await client.get("/api/v1/admin/gamification/population")).json()
    assert population["members"][0]["xp"] == 30 and population["rate_median"] > 0


async def test_level_rewards_once(gm: GamHarness) -> None:
    gm.module.config = replace(
        gm.module.config,
        level_rewards=[{"level": 2, "coins": 10}, {"level": 3, "contribution": 5, "coins": 1}],
    )
    user = gm.people["ursula"]
    curve = await gm.module.levels.curve()
    await gm.module.rewards.grant_manual(
        gm.p("boss"), user, "xp", curve.threshold(3), reason="seed", idempotency_key="lr1"
    )
    await gm.dispatch()
    assert await gm.balance(user, "coins") == 11
    assert await gm.balance(user, "contribution") == 5
    assert await gm.module.level_rewards.give(user, 3, gm.clock.now()) == 0  # never twice


async def test_tuning_api(gm: GamHarness, client: AsyncClient) -> None:
    await gm.rule("played", RULE)
    await gm.emit(gm.people["ursula"])
    await login(client, "boss")
    types = (await client.get("/api/v1/admin/gamification/event-types")).json()
    played = next(t for t in types if t["name"] == "media.played")
    assert {"name": "minutes", "numeric": True} in played["fields"]
    assert {"name": "genre", "numeric": False} in played["fields"]
    assert not any(t["name"] == "user.level_up" for t in types)

    saved = await client.put(
        "/api/v1/admin/gamification/streak", json={**STREAK, "tiers": STREAK["tiers"][::-1]}
    )
    assert saved.status_code == 200, saved.text
    assert [t["days"] for t in saved.json()["tiers"]] == [2, 5]
    assert (await client.get("/api/v1/admin/gamification/streak")).json()["enabled"] is True

    rewards = await client.put(
        "/api/v1/admin/gamification/level-rewards",
        json={"rewards": [{"level": 5, "coins": 50, "label": "Bronze"}]},
    )
    assert rewards.status_code == 200, rewards.text
    body = rewards.json()
    assert body["rewards"][0]["label"] == "Bronze" and len(body["levels"]) >= 30

    progress = (await client.get("/api/v1/admin/gamification/progress?days=30")).json()
    assert sum(d["amount"] for d in progress["days"]) == 20
    assert progress["members"][0]["gained"] == 20 and progress["members"][0]["points"][-1]["total"] == 20
    assert progress["sources"] == [{"source": "played", "amount": 20}]

    await login(client, "ursula")
    assert (await client.get("/api/v1/admin/gamification/streak")).status_code == 403
