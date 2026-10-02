"""008 T004 — filters/mode extraction; length cap; quotes/operators/SQL metacharacters kept as plain text
(never SQL); relative dates resolved in the user's time zone with their first day of the week."""

from datetime import UTC, datetime

import pytest

from portalab.capabilities.i18n import LocaleContext
from portalab.modules.search.parser.parser import InvalidFilter, QueryParser, QueryTooLong

NOW = datetime(2026, 10, 7, 22, 30, tzinfo=UTC)  # Wednesday; already Thursday in Tokyo
PARIS = LocaleContext(language="fr", locale="fr-FR", time_zone="Europe/Paris")


def parse(q: str) -> object:
    return QueryParser(max_length=64).parse(q, LocaleContext(), now=NOW)


def test_filters_and_kinds() -> None:
    q = QueryParser().parse('media type:services state:enabled connector:"fake x"', LocaleContext(), now=NOW)
    assert q.text == "media"
    assert q.kinds == ("services",)
    assert dict(q.filters) == {"state": ("enabled",), "connector": ("fake x",)}
    api = QueryParser().parse("x", LocaleContext(), now=NOW, filters={"state": ["a", "a"]}, kinds=["users"])
    assert api.kinds == ("users",) and api.filters["state"] == ("a",)


def test_normalization_and_terms() -> None:
    q = QueryParser().parse("  Élodie   Café ", LocaleContext(), now=NOW)
    assert q.text == "Élodie Café" and q.normalized == "elodie cafe" and q.terms == ("elodie", "cafe")


def test_length_cap() -> None:
    with pytest.raises(QueryTooLong) as error:
        parse("x" * 65)
    assert error.value.code == "search.query_too_long"


@pytest.mark.parametrize("q", ["'; DROP TABLE users; --", 'a" OR 1=1 --', "-foo | bar & !baz", "\x00evil"])
def test_metacharacters_are_plain_text(q: str) -> None:
    parsed = QueryParser().parse(q, LocaleContext(), now=NOW)
    assert "\x00" not in parsed.text
    assert not parsed.filters


@pytest.mark.parametrize(
    ("filters", "message"),
    [({"Bad-Name": ["x"]}, "name"), ({"state": ["x" * 65]}, "long"), ({"date": ["someday"]}, "date")],
)
def test_invalid_filters(filters: dict[str, list[str]], message: str) -> None:
    with pytest.raises(InvalidFilter) as error:
        QueryParser().parse("x", LocaleContext(), now=NOW, filters=filters)
    assert error.value.code == "search.invalid_filter"


def test_relative_dates_use_user_zone_and_week_start() -> None:
    week = QueryParser().parse("reports this week", LocaleContext(), now=NOW)
    assert week.text == "reports"
    assert week.date_from == datetime(2026, 10, 5, tzinfo=UTC) and week.date_to == datetime(
        2026, 10, 12, tzinfo=UTC
    )
    sunday_first = QueryParser().parse("date:this-week", LocaleContext(first_day_of_week=6), now=NOW)
    assert sunday_first.date_from == datetime(2026, 10, 4, tzinfo=UTC)
    tokyo = QueryParser().parse("today", LocaleContext(time_zone="Asia/Tokyo"), now=NOW)
    assert tokyo.date_from == datetime(2026, 10, 7, 15, tzinfo=UTC)  # Oct 8 00:00 JST
    french = QueryParser().parse("factures cette semaine", PARIS, now=NOW)
    assert french.text == "factures" and french.date_from == datetime(2026, 10, 4, 22, tzinfo=UTC)
    recent = QueryParser().parse("recently", LocaleContext(), now=NOW)
    assert recent.date_from is not None and (NOW - recent.date_from).days == 14


def test_explicit_dates() -> None:
    q = QueryParser().parse("after:2026-01-01 before:2026-02-01 logs", PARIS, now=NOW)
    assert q.date_from == datetime(2025, 12, 31, 23, tzinfo=UTC) and q.date_to == datetime(
        2026, 1, 31, 23, tzinfo=UTC
    )
