"""Spec 032 — the ratings of the main systems stand for an age (an unknown one is unrated), a profile's
restrictions decide what it may open and which permissions it loses, the kinds start from their presets,
PINs are 4 to 6 digits and a damaged record restricts rather than opens."""

from datetime import date

import pytest

from portalab.capabilities.household import Restrictions, age_of
from portalab.modules.identity.household.rules import (
    CHILD,
    InvalidPin,
    RestrictionSettings,
    check_pin,
    parse,
    preset,
)


@pytest.mark.parametrize(
    ("rating", "age"),
    [
        ("Tous publics", 0),
        ("U", 0),
        ("G", 0),
        ("TV-Y7", 7),
        ("PG", 8),
        ("PG-13", 13),
        ("R", 17),
        ("TV-MA", 17),
        ("NC-17", 18),
        ("12", 12),
        ("-16", 16),
        ("FSK 12", 12),
        ("12A", 12),
        ("Interdit aux moins de 18 ans", 18),
        ("NR", None),
        ("Unrated", None),
        ("", None),
        (None, None),
    ],
)
def test_ratings_stand_for_an_age(rating: str | None, age: int | None) -> None:
    assert age_of(rating) == age


def test_restrictions_decide() -> None:
    child = Restrictions(max_age=12, allow_unrated=False, blocked=frozenset({"shop", "ai"}))
    assert child.allows_age(12) and not child.allows_age(13) and not child.allows_age(None)
    assert child.withholds("marketplace.purchase") and child.withholds("ai.use")
    assert not child.withholds("media.request") and not child.withholds("news.read")
    assert Restrictions().allows_age(18) and Restrictions().allows_age(None)
    assert not Restrictions().limits_titles and child.limits_titles


def test_presets_pins_and_damaged_records() -> None:
    assert preset("child") == (CHILD, False)
    open_settings, shown = preset("standard")
    assert shown and open_settings.restrictions() == Restrictions()
    assert parse({"max_age": 13}) == CHILD  # not an offered age: restricted, never opened
    assert parse(None).max_age is None
    assert check_pin("0042") == "0042"
    for wrong in ("123", "1234567", "12a4", " 1234"):
        with pytest.raises(InvalidPin):
            check_pin(wrong)


def test_a_birth_date_holds_titles_to_the_age_of_the_day() -> None:
    born = RestrictionSettings(birth_date=date(2016, 3, 10), max_age=6, mode="lock", requests=False)
    assert born.effective_age(date(2026, 3, 9)) == 9
    assert born.effective_age(date(2026, 3, 10)) == 10  # one more at the birthday
    restrictions = born.restrictions(date(2026, 3, 10))
    assert restrictions.max_age == 10 and restrictions.mode == "lock" and not restrictions.requests
    assert (
        RestrictionSettings(birth_date=date(2000, 1, 1)).effective_age(date(2026, 1, 1)) is None
    )  # an adult
    assert (
        RestrictionSettings(max_age=12).effective_age(date(2026, 1, 1)) == 12
    )  # no birth date: the fixed age
    with pytest.raises(ValueError, match="past"):
        RestrictionSettings(birth_date=date(2999, 1, 1))


def test_the_strictest_rating_holds_and_genres_are_recognised() -> None:
    from portalab.capabilities.household import genre_of, strictest_age

    assert age_of("fr/12") == 12 and age_of("fr/TP") == 0 and age_of("de/16") == 16  # Plex's country prefix
    assert strictest_age(["12", "R", None]) == 17  # France rates Smile 12, the United States R
    assert strictest_age(["NR", None]) is None
    assert genre_of("Épouvante-horreur") == "horror" and genre_of("Horror") == "horror"
    assert genre_of("Policier") == "crime" and genre_of("Guerre") == "war"
    assert genre_of("Comédie") is None and genre_of("Science-Fiction") is None
    assert parse({"genres": ["horror", "horror"]}).genres == ["horror"]
    assert parse({"genres": ["cooking"]}) == CHILD  # not a genre one may keep out: restricted
    assert "horror" in CHILD.genres
