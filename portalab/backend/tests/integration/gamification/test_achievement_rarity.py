"""027 T091 — achievements carry a category; their unlock share is the percentage of active members who
unlocked them and the rarity derives from it; hidden achievements reveal only rarity and share."""

import pytest

from portalab.modules.gamification.achievements.evaluator import rarity_of
from tests.integration.gamification.conftest import SYSTEM, GamHarness

pytestmark = pytest.mark.integration


def test_rarity_thresholds() -> None:
    assert [rarity_of(s) for s in (80, 50, 20, 19.9, 5, 4.9, 0)] == [
        "common", "rare", "rare", "epic", "epic", "legendary", "legendary",
    ]  # fmt: skip


async def test_unlock_share_and_category(gm: GamHarness) -> None:
    gamification = gm.module
    await gamification.achievements.save(
        SYSTEM,
        "buyer",
        {
            "label": "Buyer",
            "category": "purchase",
            "criteria": [{"kind": "value_at_least", "value": "coins", "amount": 1}],
        },
    )
    await gamification.achievements.save(
        SYSTEM,
        "secret",
        {"label": "Secret", "hidden": True, "criteria": [{"kind": "level_at_least", "level": 99}]},
    )
    await gamification.rewards.unlock(gm.p("boss"), gm.people["ursula"], "buyer")
    shares = await gamification.achievements.unlock_shares()
    assert 0 < shares["buyer"] <= 100
    mine = {a["key"]: a for a in await gamification.achievements.progress(gm.people["ursula"])}
    assert mine["buyer"]["category"] == "purchase" and mine["buyer"]["state"] == "unlocked"
    assert mine["buyer"]["rarity"] == rarity_of(mine["buyer"]["unlock_share"])
    assert set(mine["secret"]) == {"key", "state", "unlock_share", "rarity"}  # nothing else leaks
