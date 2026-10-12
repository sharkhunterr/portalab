"""#81 — a booster's settings and draw: read from its product's payload (values out of bounds brought back),
as many cards as it says, never the same item twice, one at least the guaranteed rarity, a rarity with
nothing left falls back to the nearest below, the cards in no particular order; the odds shown add up to
100; the seasons never overlap and a season's booster is on sale in its weeks only."""

import random
from datetime import date

from portalab.modules.marketplace.boosters import (
    RARITIES,
    SEASONS,
    booster_info,
    booster_of,
    draw,
    odds_percent,
    on_sale,
    refund_of,
    season_now,
    until,
)

POOL = [(f"c{i}", "common") for i in range(20)] + [(f"r{i}", "rare") for i in range(6)] + [("e0", "epic")]


def test_draw_rules() -> None:
    booster = booster_of("b", {"en": "B"}, 450, {"cards": 5, "guarantee": "rare"})
    rare_at: set[int] = set()
    for seed in range(200):
        cards = draw(booster, POOL, lambda c: c[1], lambda c: c[0], random.Random(seed))  # noqa: S311 — seeded: a test
        assert len(cards) == booster.cards and len({c[0] for c in cards}) == booster.cards
        assert any(RARITIES.index(c[1]) >= RARITIES.index("rare") for c in cards)  # the guarantee
        rare_at.update(i for i, c in enumerate(cards) if c[1] != "common")
        assert all(c[1] != "legendary" for c in cards)  # none in the pool: never invented
    assert rare_at == set(range(booster.cards))  # shuffled: a rarer card turns up in every place


def test_settings_from_the_payload() -> None:
    plain = booster_of("b", {"en": "B"}, 450, {})
    assert plain.cards == 5 and plain.pool == "looks" and plain.season is None and plain.guarantee == "common"
    assert round(sum(odds_percent(plain).values())) == 100
    assert [refund_of(plain, r) for r in RARITIES] == [10, 15, 20, 30] and refund_of(plain, None) == 10
    wild = booster_of(
        "w",
        {"en": "W"},
        -5,
        {
            "cards": 99,
            "odds": {"common": -3, "epic": 4, "legendary": 1},
            "guarantee": "mythic",
            "refunds": {"rare": 1_000_000},
            "pool": "everything",
            "season": "easter",
            "per_member": 0,
        },
    )
    assert wild.cards == 10 and wild.price == 0 and wild.guarantee == "common" and wild.pool == "looks"
    assert wild.odds == {"common": 0, "rare": 0, "epic": 4, "legendary": 1} and wild.season is None
    assert wild.refunds["rare"] == 100_000 and wild.per_member is None
    empty = booster_of("e", {}, 1, {"odds": {"common": 0}})
    assert sum(empty.odds.values()) > 0  # no odds at all: the default ones
    reserve = booster_of("r", {}, 300, {"pool": "reserve"})
    assert "quota" in reserve.types and "badge" not in reserve.types
    info = booster_info("h", {}, 450, {"season": "halloween"}, date(2026, 10, 12))
    assert info["until"] == "2026-11-10" and info["kind"] == "looks"


def test_seasons() -> None:
    halloween = booster_of("h", {}, 450, {"season": "halloween"})
    christmas = booster_of("c", {}, 450, {"season": "christmas"})
    assert on_sale(halloween, date(2026, 10, 12)) and not on_sale(halloween, date(2026, 11, 11))
    assert until(halloween, date(2026, 10, 12)) == date(2026, 11, 10)
    assert on_sale(christmas, date(2026, 12, 24)) and on_sale(
        christmas, date(2027, 1, 6)
    )  # over the new year
    assert not on_sale(christmas, date(2027, 1, 7)) and until(christmas, date(2026, 12, 24)) == date(
        2027, 1, 6
    )
    assert until(booster_of("x", {}, 1, {}), date(2026, 10, 12)) is None
    for day in range(365):
        today = date.fromordinal(date(2026, 1, 1).toordinal() + day)
        current = [s for s in SEASONS.values() if s is season_now(today)]
        assert (
            len([s for s in SEASONS.values() if on_sale(booster_of("s", {}, 1, {"season": s.key}), today)])
            <= 1
        )
        assert len(current) <= 1
