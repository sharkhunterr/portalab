"""Spec 032 — the ratings of the main systems stand for an age (an unknown one is unrated), a profile's
restrictions decide what it may open and which permissions it loses, the kinds start from their presets,
PINs are 4 to 6 digits and a damaged record restricts rather than opens."""

from datetime import date

import pytest

from portalab.capabilities.household import Restrictions, age_of
from portalab.modules.household.rules import (
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
    # issue 432: any genre of the catalog, kept by its words
    assert parse({"genres": ["Science-Fiction", "Policier"]}).genres == ["crime", "science fiction"]
    assert parse({"genres": [42]}) == CHILD  # not a genre at all: restricted
    assert "horror" in CHILD.genres


def test_a_profile_may_be_kept_to_the_portal() -> None:
    from portalab.modules.media.sections.service import without_links

    assert CHILD.services is False and CHILD.restrictions().restricts
    only = RestrictionSettings(services=False).restrictions()
    assert only.restricts and not only.limits_titles  # nothing hidden, only the services' links
    assert not RestrictionSettings().restrictions().restricts
    data = {
        "sources": [{"connector": "plex", "link": "https://plex/x", "item_link": "https://plex/x"}],
        "n": 1,
    }
    assert without_links(data) == {
        "sources": [{"connector": "plex", "link": None, "item_link": None}],
        "n": 1,
    }


@pytest.mark.parametrize(
    ("rating", "age"),
    [
        ("PEGI Twelve", 12),
        ("PEGI 3", 3),
        ("ESRB E", 0),
        ("ESRB E10+", 10),
        ("ESRB T", 13),
        ("ESRB M", 17),
        ("ESRB RP", None),  # rating pending: unrated
        ("CERO D", 17),
        ("USK 6", 6),
        ("ACB MA15", 15),
        ("ACB RC", None),
        ("CLASS_IND Fourteen", 14),
        ("GRAC Fifteen", 15),
    ],
)
def test_the_games_boards_stand_for_an_age(rating: str, age: int | None) -> None:
    """Issue 421: IGDB's boards, as RomM keeps them — numbers, words and letters."""
    assert age_of(rating) == age


def test_a_weekly_plan_hours_and_a_bonus_shape_the_day() -> None:
    """Issue 432: minutes per weekday, allowed hours (overnight spans too), minutes given for one day."""
    from datetime import date, time

    from pydantic import ValidationError

    from portalab.modules.household.rules import RestrictionSettings

    plan = RestrictionSettings(
        daily_minutes=60, week_minutes=[30, 30, 30, 30, 90, 180, None], hours_from="08:00", hours_to="20:30"
    )
    today = date(2026, 11, 14)  # a Saturday
    limits = plan.restrictions(today, bonus_minutes=30, bonus_day=today)
    assert limits.minutes_on(today) == 180 + 30  # Saturday's plan and today's bonus
    assert limits.minutes_on(date(2026, 11, 15)) is None  # Sunday: no limit
    assert limits.minutes_on(date(2026, 11, 16)) == 30  # Monday, no bonus
    assert limits.allowed_at(time(9, 0)) and not limits.allowed_at(time(21, 0))
    late = RestrictionSettings(hours_from="20:00", hours_to="07:00").restrictions(today)
    assert late.allowed_at(time(23, 0)) and not late.allowed_at(time(12, 0))
    for wrong in ({"week_minutes": [30] * 6}, {"week_minutes": [2000] * 7}, {"hours_from": "25:00"}):
        try:
            RestrictionSettings(**wrong)  # type: ignore[arg-type]
        except ValidationError:
            continue
        raise AssertionError(wrong)


def test_spans_each_with_its_own_time() -> None:
    """Issue 432: spans of a weekday — a day with spans opens within them only, each its own time."""
    from datetime import UTC, date, datetime

    from pydantic import ValidationError

    from portalab.modules.household.rules import RestrictionSettings

    plan = RestrictionSettings(
        slots=[
            {"day": 5, "start": "14:00", "end": "18:00", "minutes": 60},
            {"day": 5, "start": "08:00", "end": "10:00"},
            {"day": 6, "start": "20:00", "end": "24:00", "minutes": 30},
        ]
    )
    assert [(s.day, s.start) for s in plan.slots] == [(5, "08:00"), (5, "14:00"), (6, "20:00")]
    today = date(2026, 11, 14)  # a Saturday
    limits = plan.restrictions(today, bonus_minutes=15, bonus_day=today)
    assert limits.restricts
    is_open, slot = limits.window(datetime(2026, 11, 14, 15, 0, tzinfo=UTC))
    assert is_open and slot is not None and limits.slot_minutes(slot, today) == 75  # with today's bonus
    assert limits.window(datetime(2026, 11, 14, 12, 0, tzinfo=UTC)) == (False, None)  # between two spans
    assert limits.window(datetime(2026, 11, 15, 23, 59, tzinfo=UTC))[0]  # « 24:00 »: until midnight
    assert limits.window(datetime(2026, 11, 16, 12, 0, tzinfo=UTC)) == (True, None)  # Monday: no spans, open
    for wrong in (
        [{"day": 1, "start": "10:00", "end": "09:00"}],
        [{"day": 1, "start": "10:00", "end": "12:00"}, {"day": 1, "start": "11:00", "end": "13:00"}],
        [{"day": 7, "start": "10:00", "end": "12:00"}],
        [{"day": 1, "start": "10:00", "end": "12:00", "minutes": 2}],
    ):
        try:
            RestrictionSettings(slots=wrong)  # type: ignore[arg-type]
        except ValidationError:
            continue
        raise AssertionError(wrong)


def test_the_system_countrys_rating_counts_first() -> None:
    """Issue 438: the portal's country's rating (TMDB's, the media server's « fr/… »), else the strictest."""
    from portalab.modules.media.region import country_of
    from portalab.modules.media.restrictions import local_age, own_first

    jam = [("DE", "0"), ("FR", "TP"), ("GB", "U"), ("US", "PG")]
    assert local_age(jam, "FR") == 0 and local_age(jam, "US") == 8 and local_age(jam, None) == 8
    assert local_age([("US", "PG-13"), ("server", "fr/TP")], "FR") == 0
    assert local_age([("US", "R"), ("FR", "NR")], "FR") == 17  # unrated there: the strictest of the others
    assert local_age([], "FR") is None
    assert own_first([("US", "R"), ("server", "fr/12"), ("FR", "12")], "FR")[0] == ("server", "fr/12")
    assert country_of("fr-FR") == "FR" and country_of("fr-CA") == "CA" and country_of("en_GB") == "GB"
    assert country_of("fr") == "FR" and country_of("en") == "US" and country_of("de") == "DE"
    assert country_of(None) is None and country_of("x1") is None
