"""013 T036 — leaderboards: metrics (xp, level, contribution, achievements; Coins only when enabled);
periods all-time/month/week from ledger windows; 021 visibility on the leaderboard surface (Public,
Community and Leaderboards-only appear by name, Private as anonymous entries — #66) applied at read time;
the viewer always sees their own rank; deterministic ties (earliest attainment); non-active and erased users
excluded; no private data exposed."""

from dataclasses import replace
from datetime import timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text

from portalab.modules.identity.domain.state_machine import AccountState
from tests.integration.gamification.conftest import RULE, GamHarness
from tests.integration.identity.helpers import login, module_of, set_state

pytestmark = pytest.mark.integration


async def prefer(gm: GamHarness, name: str, level: str) -> None:
    providers = gm.module.capabilities.system_providers("privacy.visibility_preference")
    provider = next(p.provider for p in providers if p.instance_ref == "gamification")
    await provider.set_preference(gm.people[name], "progression", None, level)


def board(body: dict[str, object]) -> list[tuple[int, str, int, bool]]:
    return [(e["rank"], e["display_name"], e["score"], e["me"]) for e in body["entries"]]  # type: ignore[index, union-attr]


async def test_rankings_periods_and_visibility(gm: GamHarness, client: AsyncClient, app: FastAPI) -> None:
    await gm.rule("listen", RULE)
    gm.clock.advance(timedelta(days=10))  # Sunday 2026-10-11 12:00 UTC: week from Monday 5th, month from 1st
    now = gm.clock.now()
    for at in (now - timedelta(days=8), now - timedelta(days=8, minutes=-1), now - timedelta(hours=2)):
        await gm.emit(gm.people["boss"], at=at)  # 60 XP; 20 this week; attained first
    for _ in range(3):
        await gm.emit(gm.people["ursula"])  # 60 XP, all this week
    await gm.emit(gm.people["ulrich"])  # 20 XP
    await prefer(gm, "boss", "community")
    await prefer(gm, "ursula", "leaderboard")  # leaderboards only
    await gm.module.leaderboards.refresh(force=True)

    await login(client, "ulrich")  # Private himself: still sees his own rank
    assert (await client.get("/api/v1/leaderboards")).json() == [
        "xp",
        "level",
        "contribution",
        "achievements",
    ]
    xp = (await client.get("/api/v1/leaderboards/xp")).json()
    assert board(xp) == [(1, "boss", 60, False), (2, "ursula", 60, False), (3, "ulrich", 20, True)]
    assert set(xp["entries"][0]) == {
        "rank",
        "user_id",
        "display_name",
        "score",
        "me",
        "change",
        "new",
        "anonymous",
    }
    week = (await client.get("/api/v1/leaderboards/xp", params={"period": "week"})).json()
    assert board(week) == [(1, "ursula", 60, False), (2, "boss", 20, False), (3, "ulrich", 20, True)]
    month = (await client.get("/api/v1/leaderboards/xp", params={"period": "month"})).json()
    assert [e[1] for e in board(month)] == ["boss", "ursula", "ulrich"]
    assert (await client.get("/api/v1/leaderboards/level", params={"period": "week"})).status_code == 404
    assert (await client.get("/api/v1/leaderboards/coins")).status_code == 404
    position = (await client.get("/api/v1/me/leaderboard-position", params={"metric": "xp"})).json()
    assert position == {"metric": "xp", "period": "all", "rank": 3, "score": 20}

    await login(client, "ursula")  # #66: ulrich is Private — kept in the ranking, anonymous
    seen = (await client.get("/api/v1/leaderboards/xp")).json()
    assert board(seen) == [(1, "boss", 60, False), (2, "ursula", 60, True), (3, None, 20, False)]
    hidden = seen["entries"][2]
    assert hidden["anonymous"] is True and hidden["user_id"] != str(gm.people["ulrich"])
    await prefer(gm, "boss", "private")  # read time: no recompute needed
    assert board((await client.get("/api/v1/leaderboards/xp")).json()) == [
        (1, None, 60, False),
        (2, "ursula", 60, True),
        (3, None, 20, False),
    ]
    await login(client, "boss")  # an Admin permission is not consent either
    assert board((await client.get("/api/v1/leaderboards/xp")).json()) == [
        (1, "boss", 60, True),
        (2, "ursula", 60, False),
        (3, None, 20, False),
    ]

    gm.module.config = replace(gm.module.config, leaderboard_include_coins=True)
    coins = (await client.get("/api/v1/leaderboards/coins")).json()
    assert [e[1:3] for e in board(coins)] == [("boss", 15), ("ursula", 15), (None, 5)]

    async with gm.database.unit_of_work() as uow:
        for name, key in (("ursula", "a1"), ("ursula", "a2"), ("boss", "a1")):
            await uow.session.execute(
                text(
                    "INSERT INTO gamification.user_achievements "
                    "(id, user_id, achievement_key, version, unlocked_at, transaction_ids) "
                    "VALUES (gen_random_uuid(), :u, :k, 1, :at, '[]')"
                ),
                {"u": gm.people[name], "k": key, "at": now},
            )
    await gm.module.leaderboards.compute("achievements", "all")
    assert [e[1:3] for e in board((await client.get("/api/v1/leaderboards/achievements")).json())] == [
        ("ursula", 2),
        ("boss", 1),
    ]

    await set_state(module_of(app), gm.people["ursula"], AccountState.SUSPENDED)
    await gm.module.leaderboards.compute("xp", "all")
    assert [e[1] for e in board((await client.get("/api/v1/leaderboards/xp")).json())] == ["boss", None]


async def test_refresh_cadence_and_erasure(gm: GamHarness) -> None:
    await gm.rule("listen", RULE)
    gm.clock.advance(timedelta(minutes=1))
    await gm.emit(gm.people["ursula"])
    assert await gm.module.leaderboards.refresh() == 10  # 4 metrics x 3 periods, level all-time only
    assert await gm.module.leaderboards.refresh() == 0
    gm.clock.advance(timedelta(minutes=gm.module.config.leaderboard_refresh_minutes))
    assert await gm.module.leaderboards.refresh() == 10
    from portalab.modules.gamification.privacy.participant import GamificationParticipant

    participant = GamificationParticipant(
        gm.database, gm.module.writer, clock=gm.clock, leaderboards=gm.module.leaderboards
    )
    await participant.erase(gm.people["ursula"], "final")
    view = await gm.module.leaderboards.board(gm.p("ulrich"), "xp")
    assert view.entries == () and view.me is None
    async with gm.database.session() as session:
        stored = (
            await session.execute(
                text("SELECT entries::text || previous::text FROM gamification.leaderboard_snapshots")
            )
        ).scalars()
        assert all(str(gm.people["ursula"]) not in s for s in stored)


async def test_places_gained_and_lost_since_a_day(gm: GamHarness) -> None:
    """#66: each entry tells the places gained or lost against the board of 24 hours before, among the
    members the viewer may see; a member absent the day before is new."""
    await gm.rule("listen", RULE)
    for name in ("boss", "ursula", "ulrich"):
        await prefer(gm, name, "community")
    start = gm.clock.now()
    for _ in range(3):
        await gm.emit(gm.people["boss"], at=start)  # 60 XP, first yesterday
    await gm.emit(gm.people["ursula"], at=start)  # 20 XP
    gm.clock.advance(timedelta(days=1, hours=1))
    for _ in range(4):
        await gm.emit(gm.people["ursula"])  # 100 XP: overtakes boss
    await gm.emit(gm.people["ulrich"])  # 20 XP: new today
    await gm.module.leaderboards.refresh(force=True)
    view = await gm.module.leaderboards.board(gm.p("boss"), "xp")
    moves = {e.user_id: (e.rank, e.change, e.new) for e in view.entries}
    assert moves[gm.people["ursula"]] == (1, 1, False)
    assert moves[gm.people["boss"]] == (2, -1, False)
    assert moves[gm.people["ulrich"]] == (3, None, True)
