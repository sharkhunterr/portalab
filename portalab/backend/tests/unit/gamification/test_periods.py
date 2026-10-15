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
