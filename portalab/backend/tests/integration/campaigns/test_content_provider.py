"""014 T022 — campaign-scoped achievements are offered to 013 only while the campaign is active at the
instant; unlocking and rewards happen in 013's ledger (no parallel reward path)."""

import pytest
from sqlalchemy import text

from portalab.capabilities.campaigns import CONTENT
from tests.integration.campaigns.conftest import HALLOWEEN, CampHarness, later, paris

pytestmark = pytest.mark.integration


async def test_scoped_achievements(cm: CampHarness) -> None:
    definition = {
        **HALLOWEEN,
        "achievements": [
            {
                "key": "night_watcher",
                "definition": {
                    "label": "Night watcher",
                    "criteria": [{"kind": "event_count", "event_type": "media.played", "count": 2}],
                    "rewards": [{"value": "coins", "amount": 13}],
                },
            }
        ],
    }
    await cm.create(definition=definition)
    content = cm.ev.full.identity.capabilities.system_providers(CONTENT)[0].provider
    assert await content.achievements_active_at(paris(10, 21)) == []  # not yet opened
    await cm.at(later(paris(10, 20, 0), minutes=1))
    scoped = await content.achievements_active_at(paris(10, 21))
    assert [(s.key, s.campaign, s.version) for s in scoped] == [("halloween.night_watcher", "halloween", 1)]
    user = cm.people["ursula"]
    for hour in (20, 21):
        await cm.play(user, "m2", paris(10, 22, hour))
    async with cm.database.session() as session:
        unlocked = (
            (await session.execute(text("SELECT achievement_key FROM gamification.user_achievements")))
            .scalars()
            .all()
        )
        rewards = (
            await session.execute(text("SELECT delta, source_kind FROM gamification.transactions"))
        ).all()
    assert unlocked == ["halloween.night_watcher"] and [tuple(r) for r in rewards] == [(13, "achievement")]
    await cm.at(later(paris(11, 1, 0), minutes=1))
    assert await cm.gamification.achievements.definitions(paris(11, 2)) == []
