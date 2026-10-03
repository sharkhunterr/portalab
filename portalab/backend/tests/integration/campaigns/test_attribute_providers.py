"""014 T015 — attribute providers: when the media provider is unavailable, conditions are unknown ⇒ no
boost, no crash, a diagnostic counter increments; the base grant is unaffected."""

import pytest
from sqlalchemy import text

from tests.integration.campaigns.conftest import SYSTEM, CampHarness, later, paris

pytestmark = pytest.mark.integration


async def test_unavailable_provider(cm: CampHarness) -> None:
    await cm.create()
    rule = await cm.gamification.rules.save(
        SYSTEM, "watch", {"event_type": "media.played", "grants": [{"value": "xp", "amount": 10}]}
    )
    await cm.gamification.rules.publish(SYSTEM, "watch", rule.version)
    await cm.at(later(paris(10, 20, 0), minutes=1))
    cm.media.catalog = None  # media down
    await cm.play(cm.people["ursula"], "m1", paris(10, 25, 21))
    async with cm.database.session() as session:
        delta = await session.scalar(text("SELECT delta FROM gamification.transactions"))
        failures = await session.scalar(
            text("SELECT sum(count) FROM campaigns.attribute_failures WHERE event_type = 'media.played'")
        )
    assert delta == 10 and failures >= 1
