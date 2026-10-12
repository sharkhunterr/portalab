"""#81 (proof of concept) — a booster's draw: as many cards as it says, never the same item twice, the last
at least the guaranteed rarity, a rarity with nothing left falls back to the nearest below; the cards in no
particular order; the odds shown add up to 100."""

import random

from portalab.modules.marketplace.boosters import BOOSTERS, RARITIES, draw, odds_percent, refund_of

POOL = [(f"c{i}", "common") for i in range(20)] + [(f"r{i}", "rare") for i in range(6)] + [("e0", "epic")]


def test_draw_rules() -> None:
    booster = BOOSTERS["booster_cosmos"]
    rare_at: set[int] = set()
    for seed in range(200):
        cards = draw(booster, POOL, lambda c: c[1], lambda c: c[0], random.Random(seed))  # noqa: S311 — seeded: a test
        assert len(cards) == booster.cards and len({c[0] for c in cards}) == booster.cards
        assert any(RARITIES.index(c[1]) >= RARITIES.index("rare") for c in cards)  # the guarantee
        rare_at.update(i for i, c in enumerate(cards) if c[1] != "common")
        assert all(c[1] != "legendary" for c in cards)  # none in the pool: never invented
    assert rare_at == set(range(booster.cards))  # shuffled: a rarer card turns up in every place


def test_odds_and_refund() -> None:
    odds = odds_percent(BOOSTERS["booster_cosmos"])
    assert (
        round(sum(odds.values())) == 100 and odds["legendary"] < odds["epic"] < odds["rare"] < odds["common"]
    )
    booster = BOOSTERS["booster_cosmos"]
    # fixed per rarity, whatever the price; an unknown rarity counts as common
    assert [refund_of(booster, r) for r in RARITIES] == [10, 15, 20, 30] and refund_of(booster, None) == 10
