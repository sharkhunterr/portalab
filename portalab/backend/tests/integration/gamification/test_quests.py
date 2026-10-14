"""013 T038 — quests, daily objectives and challenges: criteria over event counts; period keys in
``economy.timezone`` (DST included); daily reset; completion once per (user, quest, period); rewards
auto-granted through the ledger; ``quest.completed`` emitted once; challenges (time-boxed quests) and
campaign-linked quests only count inside their window; duplicate and late events are safe."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.capabilities.economy import DEFINITION_SOURCES, ExternalDefinition
from tests.integration.gamification.conftest import SYSTEM, GamHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration

PLAY = {"kind": "event_count", "event_type": "media.played", "count": 1}


def quest(kind: str, **overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "kind": kind,
        "label": f"A {kind}",
        "steps": [PLAY],
        "rewards": [{"value": "coins", "amount": 10}],
    }
    data.update(overrides)
    return data


async def completions(gm: GamHarness) -> list[tuple[str, str]]:
    async with gm.database.session() as session:
        rows = await session.execute(
            text(
                "SELECT payload->>'quest', payload->>'period' FROM events.events "
                "WHERE type = 'quest.completed' ORDER BY seq"
            )
        )
        return [(q, p) for q, p in rows.all()]


async def test_quest_completes_once_with_ledger_reward(gm: GamHarness, client: AsyncClient) -> None:
    await gm.module.quests.save(
        SYSTEM,
        "marathon",
        quest(
            "quest",
            steps=[
                {**PLAY, "count": 2},
                {**PLAY, "count": 1, "filter": [{"field": "genre", "op": "eq", "value": "jazz"}]},
            ],
            rewards=[{"value": "xp", "amount": 50}],
        ),
    )
    gm.clock.advance(timedelta(minutes=1))
    user = gm.people["ursula"]
    await gm.emit(user)
    await gm.emit(user)
    assert await completions(gm) == []  # the jazz step is still open
    envelope = gm.envelope(user, {"minutes": 10, "genre": "jazz"})
    await gm.module.pipeline.process(envelope)
    await gm.module.pipeline.process(envelope)  # duplicate delivery: no effect
    await gm.emit(user, {"minutes": 10, "genre": "jazz"})  # after completion: nothing more
    assert await completions(gm) == [("marathon", "once")]
    assert await gm.balance(user, "xp") == 50
    async with gm.database.session() as session:
        source = await session.scalar(
            text("SELECT source_kind FROM gamification.transactions WHERE source_ref LIKE 'quest:%'")
        )
    assert source == "quest"

    await login(client, "ursula")
    [mine] = (await client.get("/api/v1/me/quests")).json()
    assert mine["key"] == "marathon" and mine["completed_at"] is not None
    assert [s["current"] for s in mine["steps"]] == [2, 1]
    catalog = (await client.get("/api/v1/quests/catalog")).json()
    assert [q["key"] for q in catalog] == ["marathon"] and "steps" not in catalog[0]
    assert (
        await client.put("/api/v1/admin/gamification/quests/x", json={"definition": quest("daily")})
    ).status_code == 403
    await login(client, "boss")
    invalid = await client.put(
        "/api/v1/admin/gamification/quests/bad", json={"definition": quest("challenge")}
    )
    assert invalid.status_code == 422 and invalid.json()["code"] == "economy.quest_invalid"
    saved = await client.put(
        "/api/v1/admin/gamification/quests/streak", json={"definition": quest("daily", period="day")}
    )
    assert saved.status_code == 200 and saved.json()["version"] == 1
    listed = (await client.get("/api/v1/admin/gamification/quests")).json()
    assert {q["key"] for q in listed} == {"marathon", "streak"}
    assert (await client.delete("/api/v1/admin/gamification/quests/streak")).status_code == 204


async def test_daily_reset_in_economy_time_zone_across_dst(gm: GamHarness) -> None:
    gm.module.config = replace(gm.module.config, timezone="Europe/Paris")
    await gm.module.quests.save(SYSTEM, "daily_listen", quest("daily", period="day"))
    user = gm.people["ulrich"]
    # 2026-10-25: Paris leaves summer time at 03:00 (UTC+2 → UTC+1)
    for at in (
        datetime(2026, 10, 24, 22, 30, tzinfo=UTC),  # 00:30 on the 25th in Paris
        datetime(2026, 10, 25, 1, 30, tzinfo=UTC),  # 02:30 (UTC+1 now): same local day
        datetime(2026, 10, 25, 22, 30, tzinfo=UTC),  # 23:30 on the 25th: still the same day
        datetime(2026, 10, 25, 23, 30, tzinfo=UTC),  # 00:30 on the 26th: a new period
    ):
        gm.clock.set(at)
        await gm.emit(user, at=at)
    assert await completions(gm) == [("daily_listen", "2026-10-25"), ("daily_listen", "2026-10-26")]
    assert await gm.balance(user, "coins") == 20
    late = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)  # a late event lands in its own (past) day
    await gm.emit(user, at=late)
    assert (await completions(gm))[-1] == ("daily_listen", "2026-10-23")
    async with gm.database.session() as session:
        kinds = (
            (
                await session.execute(
                    text("SELECT DISTINCT source_kind FROM gamification.transactions WHERE user_id = :u"),
                    {"u": user},
                )
            )
            .scalars()
            .all()
        )
    assert list(kinds) == ["daily"]


@dataclass
class FakeCampaign:
    active: bool = True

    async def achievements(self, at: datetime) -> list[ExternalDefinition]:
        return []

    async def quests(self, at: datetime) -> list[ExternalDefinition]:
        if not self.active:
            return []
        return [
            ExternalDefinition(
                "spooky.listen", 1, quest("quest"), at - timedelta(days=1), None, "campaign:spooky:1"
            )
        ]


async def test_challenge_window_and_campaign_quests(gm: GamHarness) -> None:
    start = gm.clock.now() + timedelta(days=1)
    window = {"starts_at": start.isoformat(), "ends_at": (start + timedelta(days=2)).isoformat()}
    await gm.module.quests.save(
        SYSTEM, "weekend", quest("challenge", window=window, steps=[{**PLAY, "count": 2}])
    )
    campaign = FakeCampaign()
    gm.module.capabilities.provide(DEFINITION_SOURCES, campaign, instance_ref="fake014", owner="module:test")
    user = gm.people["ursula"]
    await gm.emit(user, at=start - timedelta(hours=1))  # before the window: not counted for the challenge
    await gm.emit(user, at=start + timedelta(hours=1))
    assert await completions(gm) == [("spooky.listen", "once")]  # the campaign quest counted the first one
    await gm.emit(user, at=start + timedelta(days=3))  # after the window
    assert [q for q, _ in await completions(gm)] == ["spooky.listen"]
    await gm.emit(user, at=start + timedelta(hours=2))
    assert [q for q, _ in await completions(gm)] == ["spooky.listen", "weekend"]

    campaign.active = False  # the campaign ended: its quest no longer counts nor shows
    other = gm.people["ulrich"]
    await gm.emit(other, at=start + timedelta(hours=3))
    assert ("spooky.listen", "once") in await completions(gm) and len(await completions(gm)) == 2
    assert [q["key"] for q in await gm.module.quests.mine(other)] == []

    from portalab.modules.gamification.privacy.participant import GamificationParticipant

    await GamificationParticipant(gm.database, gm.module.writer, clock=gm.clock).erase(user, "final")
    async with gm.database.session() as session:
        left = await session.scalar(
            text("SELECT count(*) FROM gamification.quest_progress WHERE user_id = :u"), {"u": user}
        )
    assert left == 0


async def test_completions_count_for_other_quests_and_achievements(gm: GamHarness) -> None:
    """#108: the engine's own events count — « drop by on three days » counts the daily visit's
    completions (once a day however many visits), and « complete two quests » the completions too."""
    await gm.module.quests.save(SYSTEM, "visit", quest("daily", period="day"))
    visits = {"field": "quest", "op": "eq", "value": "visit"}
    await gm.module.quests.save(
        SYSTEM,
        "regular",
        quest(
            "quest",
            steps=[{"kind": "event_count", "event_type": "quest.completed", "count": 3, "filter": [visits]}],
        ),
    )
    await gm.module.achievements.save(
        SYSTEM,
        "runner",
        {
            "label": "Runner",
            "category": "progression",
            "criteria": [{"kind": "event_count", "event_type": "quest.completed", "count": 2}],
            "rewards": [{"value": "coins", "amount": 7}],
        },
    )
    gm.clock.advance(timedelta(minutes=1))
    user = gm.people["ursula"]
    for day in range(3):
        await gm.emit(user, at=gm.clock.now() + timedelta(days=day, hours=1))
        await gm.emit(user, at=gm.clock.now() + timedelta(days=day, hours=2))  # a second visit that day
    done = await completions(gm)
    assert [q for q, _ in done].count("visit") == 3 and ("regular", "once") in done
    async with gm.database.session() as session:
        unlocked = await session.scalar(
            text("SELECT count(*) FROM gamification.user_achievements WHERE achievement_key = 'runner'")
        )
    assert unlocked == 1
