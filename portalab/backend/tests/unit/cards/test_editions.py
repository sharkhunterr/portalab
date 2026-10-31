"""Issue 233: a card's edition — the medium of its work's era — and its edition's version drawn in packs.
Issue 255: fourteen generations, and a legendary's HD version. Issue 295: its genre's version."""

import random

from portalab.modules.cards.editions import EDITIONS, edition_of
from portalab.modules.cards.packs import variant_for


def test_the_edition_follows_the_year_of_release() -> None:
    assert edition_of(None) is None
    years = (1922, 1929, 1930, 1941, 1956, 1968, 1979, 1985, 1991, 1994, 1999, 2003, 2009, 2015, 2017, 2024)
    assert [edition_of(y) for y in years] == [
        "nitrate",
        "nitrate",
        "noir",
        "noir",
        "drivein",
        "super8",
        "film",
        "laserdisc",
        "vhs",
        "zine",
        "bubble",
        "disc",
        "leather",
        "tiles",
        "stream",
        "glass",
    ]
    lasts = [last for _, last in EDITIONS]
    assert len(EDITIONS) == 14 and lasts[-1] is None and lasts[:-1] == sorted(lasts[:-1])  # type: ignore[type-var]


def test_the_editions_version_is_drawn_the_more_often_the_rarer() -> None:
    rng = random.Random(7)  # noqa: S311 — a seeded draw, for the test
    # no year of release, no edition: never its version
    drawn = {variant_for("legendary", rng, "cast") for _ in range(2000)}
    assert drawn <= {"normal", "foil", "genre", "genre_foil"}
    commons = [variant_for("common", rng, "cast", "vhs") for _ in range(6000)]
    legendaries = [variant_for("legendary", rng, "cast", "vhs") for _ in range(6000)]
    assert set(commons) <= {"normal", "foil", "showcase", "showcase_foil", "genre", "genre_foil"}
    assert 100 < sum(v.startswith("showcase") for v in commons) < 320  # about 1 in 30
    # a legendary: its HD version about 1 in 6, else its edition's about 1 in 5
    assert 850 < legendaries.count("hd") < 1150
    assert 850 < sum(v.startswith("showcase") for v in legendaries) < 1200
    # a work's borderless version is never its edition's at once
    titles = {variant_for("legendary", rng, "title", "disc") for _ in range(3000)}
    assert titles == {
        "normal",
        "foil",
        "showcase",
        "showcase_foil",
        "borderless",
        "borderless_foil",
        "hd",
        "genre",
        "genre_foil",
    }


def test_only_a_legendary_comes_in_hd() -> None:
    rng = random.Random(3)  # noqa: S311 — a seeded draw, for the test
    for rarity in ("common", "rare", "epic"):
        assert "hd" not in {variant_for(rarity, rng, "cast", "glass") for _ in range(3000)}


def test_the_genres_version_is_drawn_for_every_card_the_more_often_the_rarer() -> None:
    rng = random.Random(11)  # noqa: S311 — a seeded draw, for the test
    # a work without a year has no edition, but always a genre
    commons = [variant_for("common", rng, "cast") for _ in range(6000)]
    legendaries = [variant_for("legendary", rng, "cast") for _ in range(6000)]
    assert 100 < sum(v.startswith("genre") for v in commons) < 320  # about 1 in 30
    assert 1000 < sum(v.startswith("genre") for v in legendaries) < 1400  # about 1 in 5
    # never at once with its edition's version or the borderless one
    titles = [variant_for("epic", rng, "title", "vhs") for _ in range(6000)]
    assert all(not (v.startswith("genre") and ("showcase" in v or "borderless" in v)) for v in titles)
    assert {"genre", "genre_foil"} <= set(titles)


def test_a_booster_favours_its_own_version() -> None:
    # issue 296: a genre booster's genre version, an era booster's edition version, three times more often
    rng = random.Random(13)  # noqa: S311 — a seeded draw, for the test
    plain = [variant_for("common", rng, "cast", "vhs") for _ in range(6000)]
    favoured = [variant_for("common", rng, "cast", "vhs", "genre") for _ in range(6000)]
    era = [variant_for("common", rng, "cast", "vhs", "showcase") for _ in range(6000)]
    count = lambda drawn, base: sum(v.startswith(base) for v in drawn)  # noqa: E731
    assert count(favoured, "genre") > 2.4 * count(plain, "genre")
    assert count(era, "showcase") > 2.4 * count(plain, "showcase")
    # at most 3 in 5, however rare it is
    legendaries = [variant_for("legendary", rng, "cast", None, "genre") for _ in range(4000)]
    assert 2100 < count(legendaries, "genre") < 2700
