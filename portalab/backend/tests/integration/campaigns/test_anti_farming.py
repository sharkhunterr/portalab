"""014 T019 — boosted grants still obey 013's cooldown, caps and diminishing returns; anomalies are
recorded; the transaction keeps the campaign version in its modifier references."""

from dataclasses import replace

import pytest
from sqlalchemy import text

from tests.integration.campaigns.conftest import SYSTEM, CampHarness, later, paris

pytestmark = pytest.mark.integration


async def test_guards_bound_boosts(cm: CampHarness) -> None:
    await cm.create()
    rule = await cm.gamification.rules.save(
        SYSTEM,
        "watch",
        {
            "event_type": "media.played",
            "grants": [{"value": "xp", "amount": 10}],
            "limits": {"cooldown_seconds": 600, "caps": [{"period": "day", "max_amount": 60}]},
        },
    )
    await cm.gamification.rules.publish(SYSTEM, "watch", rule.version)
    cm.gamification.config = replace(cm.gamification.config, anomaly_max_grants_per_hour=3)
    await cm.at(later(paris(10, 20, 0), minutes=1))
    user = cm.people["ursula"]
    start = paris(10, 22, 20)
    for minutes in (0, 5, 15, 30, 45, 60, 70):
        await cm.play(user, "m1", later(start, minutes=minutes))
    async with cm.database.session() as session:
        deltas = (
            (await session.execute(text("SELECT delta FROM gamification.transactions ORDER BY seq")))
            .scalars()
            .all()
        )
        withheld = (
            (await session.execute(text("SELECT reason FROM gamification.withheld ORDER BY occurred_at")))
            .scalars()
            .all()
        )
        refs = await session.scalar(
            text("SELECT modifiers::text FROM gamification.transactions ORDER BY seq LIMIT 1")
        )
    # x2 boost (issue 223: the genre and the title count once), then the day cap; never beyond 60
    assert deltas == [20, 20, 20]
    assert "cooldown" in withheld and "cap" in withheld
    assert "campaign:halloween:1:" in str(refs)
