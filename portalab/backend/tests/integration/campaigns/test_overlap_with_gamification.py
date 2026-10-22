"""014 T018 — with the real 013 consumer: overlapping campaigns and the rule multiplier combine
multiplicatively and are capped by ``economy.maxTotalBoost``; reproducible; one grant per occurrence even
when the event is redelivered; the transaction records the campaign references."""

import pytest
from sqlalchemy import text

from tests.integration.campaigns.conftest import HALLOWEEN, SYSTEM, CampHarness, later, paris

pytestmark = pytest.mark.integration


async def test_combined_and_capped(cm: CampHarness) -> None:
    await cm.create()
    await cm.create(
        "spooky_week",
        {
            "names": {"en": "Spooky week"},
            "timezone": "Europe/Paris",
            "schedule": {"start_at": "2026-10-24T00:00:00", "end_at": "2026-10-31T00:00:00"},
            "modifiers": [{"id": "all_xp", "value": "xp", "factor": 2.5}],
        },
    )
    rule = await cm.gamification.rules.save(
        SYSTEM,
        "watch",
        {
            "event_type": "media.played",
            "multiplier": 1.2,
            "grants": [{"value": "xp", "amount": 10}, {"value": "coins", "amount": 10}],
        },
    )
    await cm.gamification.rules.publish(SYSTEM, "watch", rule.version)
    await cm.at(later(paris(10, 24, 0), minutes=1))
    user = cm.people["ursula"]
    # issue 223: the horror genre and the title are Halloween's themed bonuses — the film earns one of them
    await cm.play(user, "m1", paris(10, 25, 21))  # 1.2 · 2 · 2.5 = 6 → capped at 5
    await cm.play(user, "m2", paris(10, 25, 22))  # comedy: 1.2 · 2.5 = 3
    async with cm.database.session() as session:
        rows = (
            await session.execute(
                text("SELECT value, delta, multiplier, modifiers FROM gamification.transactions ORDER BY seq")
            )
        ).all()
    xp, coins, comedy_xp, comedy_coins = rows
    assert (xp.value, xp.delta, float(xp.multiplier)) == ("xp", 50, 5.0) and xp.modifiers["capped"] is True
    assert {m["source_ref"] for m in xp.modifiers["applied"]} == {
        "rule",
        "campaign:halloween:1:horror_xp",
        "campaign:spooky_week:1:all_xp",
    }
    assert (coins.delta, float(coins.multiplier)) == (18, 1.8)
    assert (comedy_xp.delta, comedy_coins.delta) == (30, 12)
    async with cm.database.session() as session:
        event = (
            (
                await session.execute(
                    text("SELECT * FROM events.events WHERE type = 'media.played' ORDER BY seq LIMIT 1")
                )
            )
            .mappings()
            .one()
        )
    from portalab.capabilities.events import Envelope

    replay = Envelope(
        event_id=event["event_id"],
        seq=event["seq"],
        type="media.played",
        type_version=1,
        occurred_at=event["occurred_at"],
        received_at=event["received_at"],
        source_system="test",
        source_event_id=None,
        actor_user_id=user,
        actor_kind="user",
        subject_type=None,
        subject_id=None,
        payload=event["payload"],
        provenance={},
        correlation_id=None,
    )
    assert (await cm.gamification.pipeline.process(replay)).granted == 0
    assert HALLOWEEN["modifiers"][0]["factor"] == 2
