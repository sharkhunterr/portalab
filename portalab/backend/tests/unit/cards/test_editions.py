"""Issue 233: a card's edition — the medium of its work's era — and its edition's version drawn in packs."""

import random

from portalab.modules.cards.editions import edition_of
from portalab.modules.cards.packs import variant_for


def test_the_edition_follows_the_year_of_release() -> None:
    assert edition_of(None) is None
    assert [edition_of(y) for y in (1939, 1979, 1980, 1996, 1997, 2009, 2010, 2026)] == [
        "film",
        "film",
        "vhs",
        "vhs",
        "disc",
        "disc",
        "stream",
        "stream",
    ]


def test_the_editions_version_is_drawn_the_more_often_the_rarer() -> None:
    rng = random.Random(7)  # noqa: S311 — a seeded draw, for the test
    # no year of release, no edition: never its version
    assert {variant_for("legendary", rng, "cast") for _ in range(2000)} <= {"normal", "foil"}
    commons = [variant_for("common", rng, "cast", "vhs") for _ in range(6000)]
    legendaries = [variant_for("legendary", rng, "cast", "vhs") for _ in range(6000)]
    assert set(commons) <= {"normal", "foil", "showcase", "showcase_foil"}
    assert 100 < sum(v.startswith("showcase") for v in commons) < 320  # about 1 in 30
    assert 1000 < sum(v.startswith("showcase") for v in legendaries) < 1400  # about 1 in 5
    # a work's borderless version is never its edition's at once
    titles = {variant_for("legendary", rng, "title", "disc") for _ in range(3000)}
    assert titles == {"normal", "foil", "showcase", "showcase_foil", "borderless", "borderless_foil"}
