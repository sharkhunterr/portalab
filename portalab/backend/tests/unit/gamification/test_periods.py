"""#128 — the leaderboard periods: each starts on a day boundary in the economy's time zone."""

from datetime import UTC, datetime

from portalab.modules.gamification.leaderboards.periods import period_start


def test_every_period_starts_where_it_should() -> None:
    now = datetime(2026, 10, 15, 9, 30, tzinfo=UTC)  # a Thursday
    start = {p: period_start(p, now, "UTC") for p in ("all", "week", "month", "6months", "year", "3years")}
    assert start["all"] is None
    assert start["week"] == datetime(2026, 10, 12, tzinfo=UTC)
    assert start["month"] == datetime(2026, 10, 1, tzinfo=UTC)
    assert start["6months"] == datetime(2026, 5, 1, tzinfo=UTC)
    assert start["year"] == datetime(2026, 1, 1, tzinfo=UTC)
    assert start["3years"] == datetime(2024, 1, 1, tzinfo=UTC)


def test_six_months_across_a_new_year() -> None:
    assert period_start("6months", datetime(2026, 3, 2, 12, tzinfo=UTC), "UTC") == datetime(
        2025, 10, 1, tzinfo=UTC
    )
    paris = period_start("year", datetime(2026, 6, 1, 12, tzinfo=UTC), "Europe/Paris")
    assert paris == datetime(2025, 12, 31, 23, tzinfo=UTC)  # midnight in Paris


def test_an_objective_starts_again_at_its_period_end() -> None:
    """#307: a daily, weekly or monthly objective starts again at the next local midnight, Monday or first
    of the month; a quest done once never does."""
    from portalab.modules.gamification.quests.periods import period_end

    now = datetime(2026, 12, 31, 23, 30, tzinfo=UTC)  # a Thursday; already 2027 in Paris
    assert period_end("none", now, "UTC") is None
    assert period_end("day", now, "UTC") == datetime(2027, 1, 1, tzinfo=UTC)
    assert period_end("week", now, "UTC") == datetime(2027, 1, 4, tzinfo=UTC)
    assert period_end("month", now, "UTC") == datetime(2027, 1, 1, tzinfo=UTC)
    assert period_end("day", now, "Europe/Paris") == datetime(2027, 1, 1, 23, tzinfo=UTC)
    assert period_end("month", now, "Europe/Paris") == datetime(2027, 1, 31, 23, tzinfo=UTC)
    # the night the clocks go back in Paris, midnight is still midnight
    assert period_end("day", datetime(2026, 10, 25, 12, tzinfo=UTC), "Europe/Paris") == datetime(
        2026, 10, 25, 23, tzinfo=UTC
    )
