"""#81 (proof of concept) — a booster's draw: as many cards as it says, never the same item twice, the last
at least the guaranteed rarity, a rarity with nothing left falls back to the nearest below; revealed from the
plainest to the rarest; the odds shown add up to 100."""

import random

from portalab.modules.marketplace.boosters import BOOSTERS, RARITIES, draw, odds_percent, refund_of

POOL = [(f"c{i}", "common") for i in range(20)] + [(f"r{i}", "rare") for i in range(6)] + [("e0", "epic")]


def test_draw_rules() -> None:
    booster = BOOSTERS["booster_cosmos"]
    for seed in range(200):
        cards = draw(booster, POOL, lambda c: c[1], lambda c: c[0], random.Random(seed))  # noqa: S311 — seeded: a test
        assert len(cards) == booster.cards and len({c[0] for c in cards}) == booster.cards
        assert any(RARITIES.index(c[1]) >= RARITIES.index("rare") for c in cards)  # the guarantee
        assert [RARITIES.index(c[1]) for c in cards] == sorted(RARITIES.index(c[1]) for c in cards)
        assert all(c[1] != "legendary" for c in cards)  # none in the pool: never invented


def test_odds_and_refund() -> None:
    odds = odds_percent(BOOSTERS["booster_cosmos"])
    assert (
        round(sum(odds.values())) == 100 and odds["legendary"] < odds["epic"] < odds["rare"] < odds["common"]
    )
    assert refund_of(400) == 100 and refund_of(None) == 10  # a quarter of the price, at least 10
