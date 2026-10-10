"""#54/#55 — perks bought in the shop: a streak freeze covers a missed day (the streak and its multiplier go
on), used automatically and only once; a boost multiplies the gains for a while, the next one queued after
it, shown on the member's progression and in the gains' sources."""

from dataclasses import replace
from datetime import timedelta

import pytest
from httpx import AsyncClient

from portalab.capabilities.economy import PERKS
from tests.integration.gamification.conftest import RULE, GamHarness
from tests.integration.gamification.test_streaks_levels import STREAK
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_a_freeze_covers_one_missed_day(gm: GamHarness) -> None:
    gm.module.config = replace(gm.module.config, streak=STREAK)
    await gm.rule("played", RULE)
    user = gm.people["ursula"]
    perks = gm.module.perks
    assert gm.module.capabilities.system_providers(PERKS)[0].provider is perks
    await perks.grant_freezes(user, 1, "marketplace:o1")
    await perks.grant_freezes(user, 1, "marketplace:o1")  # replayed: granted once
    assert await perks.freezes_available(user) == 1

    start = gm.clock.now() + timedelta(hours=1)
    await gm.emit(user, at=start)
    await gm.emit(user, at=start + timedelta(days=1))
    # day 2 missed; on day 3 the hourly check covers it
    assert await perks.apply_freezes(start + timedelta(days=3)) == 1
    assert await perks.apply_freezes(start + timedelta(days=3)) == 0  # never twice
    assert await perks.freezes_available(user) == 0
    state = await perks.state(user, start + timedelta(days=3))
    assert state["freezes"] == 0 and state["last_frozen"] is not None
    await gm.emit(user, at=start + timedelta(days=3))
    streak = await gm.module.streaks.current(user, start + timedelta(days=3))
    assert streak["days"] == 4  # the frozen day counts: the streak goes on

    # no freeze left: the next missed day is not covered
    assert await perks.apply_freezes(start + timedelta(days=5)) == 0


async def test_no_freeze_without_a_streak(gm: GamHarness) -> None:
    gm.module.config = replace(gm.module.config, streak=STREAK)
    user = gm.people["ursula"]
    await gm.module.perks.grant_freezes(user, 2, "marketplace:o2")
    assert await gm.module.perks.apply_freezes(gm.clock.now() + timedelta(days=2)) == 0
    assert await gm.module.perks.freezes_available(user) == 2


async def test_a_boost_multiplies_and_queues(gm: GamHarness, client: AsyncClient) -> None:
    await gm.rule("played", RULE)
    user = gm.people["ursula"]
    perks = gm.module.perks
    await perks.grant_boost(user, 2, 24, ["xp"], "marketplace:b1")
    await perks.grant_boost(user, 1.5, 24, ["xp"], "marketplace:b2")  # starts when the first ends
    await perks.grant_boost(user, 1.5, 24, ["xp"], "marketplace:b2")  # replayed: ignored
    await gm.emit(user)
    assert await gm.balance(user) == 40  # 20 · 2
    assert await gm.balance(user, "coins") == 5  # not a boosted value
    state = await perks.state(user)
    assert state["boost"]["factor"] == 2.0
    assert state["boost"]["until"] > state["boost"]["ends_at"]  # the queued one follows
    await gm.emit(user, at=gm.clock.now() + timedelta(hours=30))
    assert await gm.balance(user) == 40 + 30  # the second boost, x1.5
    await gm.emit(user, at=gm.clock.now() + timedelta(hours=50))
    assert await gm.balance(user) == 70 + 20  # all over

    await login(client, "ursula")
    progression = (await client.get("/api/v1/me/progression")).json()
    assert progression["boost"]["factor"] == 2.0 and progression["boost"]["gains"] == ["xp"]
    sources = (await client.get("/api/v1/me/progression/sources?value=xp&days=30")).json()
    assert any(s["source"] == "boost" for s in sources["sources"])
    streak = (await client.get("/api/v1/me/streak")).json()
    assert streak["freezes"] == 0 and streak["last_frozen"] is None
