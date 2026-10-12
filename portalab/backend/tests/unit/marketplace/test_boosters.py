"""#81 — a booster's draw: as many cards as it says, never the same item twice, the last
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


def test_boosters_on_sale_and_seasons() -> None:
    from datetime import date

    from portalab.modules.marketplace.boosters import on_sale, until

    for booster in BOOSTERS.values():
        assert booster.guarantee in RARITIES and sum(booster.odds.values()) > 0 and booster.cards >= 1
        assert set(booster.odds) <= set(RARITIES) and booster.price > 0
    always = {k for k, b in BOOSTERS.items() if b.window is None}
    assert always == {
        "booster_cosmos",
        "booster_legend",
        "booster_prestige",
        "booster_reserve",
        "booster_discovery",
    }
    assert BOOSTERS["booster_legend"].price > 5 * BOOSTERS["booster_cosmos"].price  # really dearer
    halloween, winter = BOOSTERS["booster_halloween"], BOOSTERS["booster_winter"]
    assert on_sale(halloween, date(2026, 10, 12)) and not on_sale(halloween, date(2026, 11, 11))
    assert until(halloween, date(2026, 10, 12)) == date(2026, 11, 10)
    # over the new year
    assert on_sale(winter, date(2026, 12, 24)) and on_sale(winter, date(2027, 1, 6))
    assert not on_sale(winter, date(2027, 1, 7)) and until(winter, date(2026, 12, 24)) == date(2027, 1, 6)
    assert until(BOOSTERS["booster_cosmos"], date(2026, 10, 12)) is None
    # at most one season at a time, never two
    for day in range(365):
        today = date(2026, 1, 1).toordinal() + day
        seasons = [b for b in BOOSTERS.values() if b.window and on_sale(b, date.fromordinal(today))]
        assert len(seasons) <= 1
