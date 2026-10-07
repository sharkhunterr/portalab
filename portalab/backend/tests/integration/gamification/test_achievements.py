"""013 T025 — achievements: event-count, level and value criteria; unlocked exactly once (also under
concurrent events); rewards through the ledger (``source_kind=achievement``); ``achievement.unlocked``
emitted; hidden achievements not revealed in the catalog until unlocked."""

import asyncio
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.gamification.conftest import SYSTEM, GamHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_unlock_once_with_rewards(gm: GamHarness, client: AsyncClient) -> None:
    await gm.module.achievements.save(
        SYSTEM,
        "rock_fan",
        {
            "label": "Rock fan",
            "criteria": [
                {
                    "kind": "event_count",
                    "event_type": "media.played",
                    "filter": [{"field": "genre", "value": "rock"}],
                    "count": 3,
                }
            ],
            "rewards": [{"value": "coins", "amount": 25}],
        },
    )
    await gm.module.achievements.save(
        SYSTEM,
        "secret",
        {
            "label": "Night owl",
            "hidden": True,
            "criteria": [{"kind": "value_at_least", "value": "coins", "amount": 20}],
        },
    )
    await gm.module.achievements.save(
        SYSTEM, "veteran", {"label": "Veteran", "criteria": [{"kind": "level_at_least", "level": 5}]}
    )
    user = gm.people["ursula"]
    gm.clock.advance(timedelta(seconds=1))
    await login(client, "ursula")
    catalog = (await client.get("/api/v1/achievements/catalog")).json()
    assert {"key": "secret", "hidden": True} in catalog and all(
        "label" not in c for c in catalog if c["key"] == "secret"
    )
    envelopes = [
        gm.envelope(user, {"minutes": 1, "genre": "rock"}, at=gm.clock.now() + timedelta(seconds=i + 1))
        for i in range(6)
    ]
    await asyncio.gather(*(gm.module.pipeline.process(e) for e in envelopes))
    await gm.module.pipeline.process(gm.envelope(user, {"minutes": 1, "genre": "pop"}))
    async with gm.database.session() as session:
        unlocked = (
            (
                await session.execute(
                    text(
                        "SELECT achievement_key FROM gamification.user_achievements ORDER BY achievement_key"
                    )
                )
            )
            .scalars()
            .all()
        )
        rewards = (
            await session.execute(text("SELECT delta, source_kind FROM gamification.transactions"))
        ).all()
        events = (
            (
                await session.execute(
                    text(
                        "SELECT payload->>'achievement' FROM events.events "
                        "WHERE type = 'achievement.unlocked'"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert unlocked == ["rock_fan", "secret"]  # 25 coins unlocked the hidden "secret" right after
    assert [tuple(r) for r in rewards] == [(25, "achievement")]
    assert sorted(events) == ["rock_fan", "secret"]
    mine = {a["key"]: a for a in (await client.get("/api/v1/me/achievements")).json()}
    assert mine["rock_fan"]["state"] == "unlocked" and mine["secret"]["label"] == "Night owl"
    assert mine["veteran"]["state"] == "locked"
    await gm.module.rewards.grant_manual(gm.p("boss"), user, "xp", 1000, reason="seed", idempotency_key="lvl")
    assert (await client.get("/api/v1/me/progression")).json()["achievements"] == 3


async def test_unlock_notification_names_the_achievement(gm: GamHarness) -> None:
    """027: the member is told the achievement's name and what it rewards — never its technical key."""
    from portalab.capabilities.notifications import NOTIFY
    from tests.integration.gamification.test_reward_consumer import Outbox

    outbox = Outbox()
    gm.ev.full.identity.capabilities.provide(NOTIFY, outbox, instance_ref="t", owner="test")
    await gm.module.achievements.save(
        SYSTEM,
        "first_play",
        {
            "label": "First play",
            "description": "Play something once.",
            "criteria": [{"kind": "event_count", "event_type": "media.played", "count": 1}],
        },
    )
    gm.clock.advance(timedelta(seconds=1))
    await gm.module.pipeline.process(gm.envelope(gm.people["ursula"], {"minutes": 1, "genre": "rock"}))
    [note] = [r for r in outbox.sent if r.category == "gamification.achievement"]
    assert note.params == {"achievement": "First play", "description": "Play something once."}


async def test_some_achievements_unlock_cosmetics(gm: GamHarness) -> None:
    """027: an achievement may give shop products (a badge, a title…) — offered once committed, through the
    shop's gifts; the level-up moment lists the achievements just unlocked and what they gave."""
    from dataclasses import replace
    from typing import Any

    from portalab.capabilities.marketplace import GIFTS
    from portalab.modules.gamification.progression.level_up import level_up_summary

    class _Gifts:
        def __init__(self) -> None:
            self.given: list[tuple[Any, str]] = []

        async def gift(self, user: Any, product_key: str, reason: str) -> bool:
            self.given.append((user, product_key))
            return True

    gifts = _Gifts()
    gm.ev.full.identity.capabilities.provide(GIFTS, gifts, instance_ref="t", owner="test")
    await gm.module.achievements.save(
        SYSTEM,
        "collector_test",
        {
            "label": "The Collector",
            "criteria": [{"kind": "event_count", "event_type": "media.played", "count": 1}],
            "rewards": [{"value": "coins", "amount": 50}],
            "unlocks": [
                {"product": "badge_completionist", "kind": "badge", "label": "The Collector"},
                {"product": "title_completionist", "kind": "title", "label": "The Collector"},
            ],
        },
    )
    user = gm.people["ursula"]
    gm.clock.advance(timedelta(seconds=1))
    await gm.module.pipeline.process(gm.envelope(user, {"minutes": 1, "genre": "rock"}))
    assert gifts.given == [(user, "badge_completionist"), (user, "title_completionist")]
    config = replace(gm.module.config, level_rewards=[{"level": 3, "coins": 100, "label": "Level 3"}])
    summary = await level_up_summary(
        gm.database, gm.module.levels, gm.module.achievements, config, user, 3, 1, clock=gm.clock
    )
    assert [t["coins"] for t in summary["rewards"]] == [100]  # every tier crossed
    [unlocked] = [a for a in summary["achievements"] if a["key"] == "collector_test"]
    assert [u["product"] for u in unlocked["unlocks"]] == ["badge_completionist", "title_completionist"]
    assert unlocked["rewards"] == [{"value": "coins", "amount": 50}]
