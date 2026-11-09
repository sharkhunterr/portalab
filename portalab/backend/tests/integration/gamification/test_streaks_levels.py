"""027 — play streaks multiply the rewards of counted events by the highest tier reached (a missed day
starts over); level rewards give Coins/Contribution once per tier reached; the tuning endpoints."""

from dataclasses import replace
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.modules.gamification.progression.sources import split
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
        level_rewards=[{"level": 2, "coins": 10}, {"level": 3, "contribution": 5, "coins": 1, "xp": 7}],
    )
    user = gm.people["ursula"]
    curve = await gm.module.levels.curve()
    await gm.module.rewards.grant_manual(
        gm.p("boss"), user, "xp", curve.threshold(3), reason="seed", idempotency_key="lr1"
    )
    await gm.dispatch()
    assert await gm.balance(user, "coins") == 11
    assert await gm.balance(user, "contribution") == 5
    assert await gm.balance(user) == curve.threshold(3) + 7  # #108: a tier may give a little XP too
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
    # #309: achievements and quests may also count the progression itself (a quest done twenty days…)
    goals = (await client.get("/api/v1/admin/gamification/event-types?goals=true")).json()
    done = next(t for t in goals if t["name"] == "quest.completed")
    assert {"name": "quest", "numeric": False} in done["fields"]
    assert not any(t["name"] == "reward.granted" for t in goals)

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

    # #104: each member's progression — by kind of gain, day by day, and their running balance; one of them
    await gm.emit(gm.people["boss"])
    members = (await client.get("/api/v1/admin/gamification/members?days=30")).json()["members"]
    ursula = next(m for m in members if m["user_id"] == str(gm.people["ursula"]))
    assert ursula["balance"] == 20 and ursula["gained"] == 20
    assert ursula["sources"] == [{"source": "media", "amount": 20}]  # a play
    assert sum(sum(d["amounts"].values()) for d in ursula["days"]) == 20
    assert ursula["points"][0]["total"] == 0 and ursula["points"][-1]["total"] == 20
    assert {m["user_id"] for m in members} == {str(gm.people["ursula"]), str(gm.people["boss"])}
    one = await client.get("/api/v1/admin/gamification/members", params={"member": str(gm.people["boss"])})
    assert [m["user_id"] for m in one.json()["members"]] == [str(gm.people["boss"])]

    # #106: each member's detail — held, gained, spent, the levels reached and when, day by day
    for _ in range(4):
        await gm.emit(gm.people["ursula"])  # 100 XP: level 2
    taken = await client.post(
        "/api/v1/admin/gamification/manual-withdrawals",
        json={"user_id": str(gm.people["ursula"]), "value": "coins", "amount": 3, "reason": "test"},
    )
    assert taken.status_code in (200, 201), taken.text
    details = (await client.get("/api/v1/admin/gamification/members/details?days=30")).json()["members"]
    assert details[0]["user_id"] == str(gm.people["ursula"])  # the most advanced first
    mine = details[0]
    assert mine["xp"] == {"balance": 100, "gained": 100, "spent": 0}
    assert mine["coins"] == {"balance": 22, "gained": 22, "spent": 0}  # a withdrawal corrects the gains
    assert mine["start_level"] == 1 and mine["level"] == 2 and [u["level"] for u in mine["level_ups"]] == [2]
    [today] = mine["days"]
    assert today["xp"] == 100 and today["coins"] == 22 and today["levels"] == [2]
    alone = await client.get(
        "/api/v1/admin/gamification/members/details", params={"member": str(gm.people["boss"])}
    )
    assert [m["user_id"] for m in alone.json()["members"]] == [str(gm.people["boss"])]

    # #107: every operation of every member, the latest first, with the balance and the level after it
    ops = (await client.get("/api/v1/admin/gamification/operations?days=30")).json()
    assert ops["next_cursor"] is None and len(ops["items"]) == 6 * 2 + 1  # 6 plays (XP + Coins), a withdrawal
    assert ops["total"] == 13
    times = [o["occurred_at"] for o in ops["items"]]
    assert times == sorted(times, reverse=True)
    [taken] = [o for o in ops["items"] if o["kind"] == "correction"]
    assert taken["delta"] == -3 and taken["reason"] == "test" and taken["source"] == "admin"
    assert taken["level"] is None
    xp = [o for o in ops["items"] if o["value"] == "xp" and o["user_id"] == str(gm.people["ursula"])]
    assert [o["balance"] for o in xp] == [100, 80, 60, 40, 20]
    assert [o["level_up"] for o in xp] == [True, False, False, False, False] and xp[0]["level"] == 2
    assert xp[0]["source"] == "media" and xp[0]["label"] == "played"
    seen, cursor = [], None  # page by page, none lost nor repeated
    while True:
        page = (
            await client.get(
                "/api/v1/admin/gamification/operations",
                params={"limit": 5, **({"cursor": cursor} if cursor else {})},
            )
        ).json()
        seen += [o["id"] for o in page["items"]]
        if not (cursor := page["next_cursor"]):
            break
    assert seen == [o["id"] for o in ops["items"]]
    theirs = await client.get(
        "/api/v1/admin/gamification/operations",
        params={"member": str(gm.people["boss"]), "value": "coins"},
    )
    boss = [(o["name"] is not None, o["delta"], o["balance"]) for o in theirs.json()["items"]]
    assert boss == [(True, 5, 5)] and theirs.json()["total"] == 1

    await login(client, "ursula")
    assert (await client.get("/api/v1/admin/gamification/streak")).status_code == 403
    assert (await client.get("/api/v1/admin/gamification/members")).status_code == 403
    assert (await client.get("/api/v1/admin/gamification/members/details")).status_code == 403
    assert (await client.get("/api/v1/admin/gamification/operations")).status_code == 403
    # #114: my own journal — the same rows, mine only
    mine = (await client.get("/api/v1/me/progression/operations", params={"value": "xp"})).json()
    assert {o["user_id"] for o in mine["items"]} == {str(gm.people["ursula"])}
    assert [o["balance"] for o in mine["items"]] == [100, 80, 60, 40, 20] and mine["total"] == 5


def test_split_bonus() -> None:
    from portalab.modules.gamification.progression.sources import split

    modifiers = {
        "applied": [
            {"source_ref": "rule", "factor": 1.0},
            {"source_ref": "streak:5d", "factor": 2.0},
            {"source_ref": "campaign:halloween:1:horror_xp", "factor": 2.0},
        ]
    }
    # base 20, x4 → 80: the action keeps 20, streak and campaign share the 60 extra equally
    assert split("reward_rule", 80, 20, modifiers, "media") == {"media": 20, "streak": 30, "campaigns": 30}
    assert split("quest", 50, 50, {}, "quests") == {"quests": 50}


async def test_my_sources(gm: GamHarness, client: AsyncClient) -> None:
    gm.module.config = replace(gm.module.config, streak=STREAK)
    await gm.rule("played", RULE)
    user = gm.people["ursula"]
    start = gm.clock.now() + timedelta(hours=1)
    for day in (0, 1):
        await gm.emit(user, at=start + timedelta(days=day))
    gm.clock.set(start + timedelta(days=1, hours=1))
    await login(client, "ursula")
    body = (await client.get("/api/v1/me/progression/sources?days=30")).json()
    by_source = {s["source"]: s["amount"] for s in body["sources"]}
    assert body["total"] == 50 and by_source == {"media": 40, "streak": 10}  # media.played is a media action
    assert [d["amounts"] for d in body["days"]][-1] == {"media": 20, "streak": 10}


async def test_operations_tell_their_bonuses(gm: GamHarness, client: AsyncClient) -> None:
    """The journal names the bonuses inside a gain, as the charts split them (admin's and my own)."""
    gm.module.config = replace(gm.module.config, streak=STREAK)
    await gm.rule("played", RULE)
    user = gm.people["ursula"]
    start = gm.clock.now() + timedelta(hours=1)
    for day in (0, 1):
        await gm.emit(user, at=start + timedelta(days=day))
    gm.clock.set(start + timedelta(days=1, hours=1))
    await login(client, "ursula")
    mine = (await client.get("/api/v1/me/progression/operations", params={"value": "xp"})).json()["items"]
    assert [(o["delta"], o["source"], o["bonuses"]) for o in mine] == [
        # 20 · 1.5: the streak's 10 named, and (#258) its multiplier
        (30, "media", [{"source": "streak", "amount": 10.0, "factor": 1.5}]),
        (20, "media", []),
    ]
    await login(client, "boss")
    ops = (await client.get("/api/v1/admin/gamification/operations", params={"value": "xp"})).json()["items"]
    assert ops[0]["bonuses"] == [{"source": "streak", "amount": 10.0, "factor": 1.5}]  # #258: its 1.5 too


async def test_rewards_follow_the_streak(gm: GamHarness) -> None:
    """Issue 226: a level's reward (like a quest's, an achievement's) follows the streak alive — read, never
    counted — with its detail in the ledger; left out of ``reward_bonuses``, it keeps its amount."""
    gm.module.config = replace(gm.module.config, streak=STREAK, level_rewards=[{"level": 2, "xp": 10}])
    await gm.rule("played", RULE)
    user = gm.people["ursula"]
    start = gm.clock.now() + timedelta(hours=1)
    for day in (0, 1):
        await gm.emit(user, at=start + timedelta(days=day))  # a 2-day streak: x1.5
    before = await gm.balance(user)
    assert await gm.module.level_rewards.give(user, 2, start + timedelta(days=1, hours=2)) == 1
    assert await gm.balance(user) == before + 15
    async with gm.database.session() as session:
        row = (
            await session.execute(
                text(
                    "SELECT base_amount, delta, modifiers FROM gamification.transactions "
                    "WHERE source_kind = 'level_reward'"
                )
            )
        ).one()
    assert row.base_amount == 10 and row.delta == 15
    assert any(m["source_ref"].startswith("streak:") for m in row.modifiers["applied"])
    assert split("level_reward", 15, 10, row.modifiers, "levels") == {"levels": 10.0, "streak": 5.0}
    # a streak is never kept alive by a reward: the next day, nothing counted, it is still yesterday's
    state = await gm.module.streaks.current(user, start + timedelta(days=1, hours=3))
    assert state["days"] == 2

    other = gm.people["boss"]
    gm.module.config = replace(gm.module.config, reward_bonuses=[])
    for day in (0, 1):
        await gm.emit(other, at=start + timedelta(days=day))
    before = await gm.balance(other)
    await gm.module.level_rewards.give(other, 2, start + timedelta(days=1, hours=2))
    assert await gm.balance(other) == before + 10


async def test_a_streak_tells_its_days_its_record_and_its_road(gm: GamHarness, client: AsyncClient) -> None:
    """#388, #389: a streak as its page draws it: its last days (done, missed, today still to come), its
    record, its tiers; the administrators see every member's, the longest streaks now first — and only
    they do."""
    gm.module.config = replace(gm.module.config, streak=STREAK)
    await gm.rule("played", RULE)
    ursula, ulrich = gm.people["ursula"], gm.people["ulrich"]
    start = gm.clock.now() + timedelta(hours=1)
    for day in (0, 1, 2, 3, 4, 7, 8):  # five days, two missed, then two days again
        await gm.emit(ursula, at=start + timedelta(days=day))
    await gm.emit(ulrich, at=start + timedelta(days=9))
    today = start + timedelta(days=9)  # Ursula has not played yet today: her streak still lives

    state = await gm.module.streaks.current(ursula, today)
    assert (state["days"], state["best"], state["today"], state["multiplier"]) == (2, 5, False, 1.5)
    assert state["next"] == {"days": 5, "multiplier": 2.0} and [t["days"] for t in state["tiers"]] == [2, 5]
    assert [d["state"] for d in state["recent"]][-10:] == [
        "done",
        "done",
        "done",
        "done",
        "done",
        "missed",
        "missed",
        "done",
        "done",
        "pending",
    ]
    assert len(state["recent"]) == 14 and state["recent"][-1]["day"] == today.date()

    board = await gm.module.streaks.board(today)
    assert [(user, s["days"], s["today"]) for user, s in board] == [(ursula, 2, False), (ulrich, 1, True)]

    await login(client, "boss")
    members = (await client.get("/api/v1/admin/gamification/streaks")).json()
    assert {m["user_id"] for m in members} == {str(ursula), str(ulrich)}
    assert all(m["name"] and len(m["recent"]) == 14 for m in members)
    await login(client, "ursula")
    mine = (await client.get("/api/v1/me/streak")).json()
    assert {"tiers", "best", "today", "recent"} <= set(mine)
    assert (await client.get("/api/v1/admin/gamification/streaks")).status_code == 403
