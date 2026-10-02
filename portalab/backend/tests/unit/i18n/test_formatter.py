"""026 T020/T034 — formats follow the *locale*, independent from the language; hour cycle and first day of
week overrides; presentation helpers never alter values."""

from datetime import UTC, date, datetime

from portalab.capabilities.i18n import LocaleContext
from portalab.modules.i18n.adapters.presentation import Presentation
from portalab.modules.i18n.format.formatter import Formatter

F = Formatter()
INSTANT = datetime(2026, 10, 3, 15, 5, tzinfo=UTC)


def ctx(locale: str, **extra: object) -> LocaleContext:
    return LocaleContext(language="en", locale=locale, **extra)  # type: ignore[arg-type]


def test_numbers_and_dates_follow_locale() -> None:
    assert F.number(1234.5, ctx("en-US")) == "1,234.5"
    assert F.number(1234.5, ctx("de-DE")) == "1.234,5"
    assert F.date(date(2026, 10, 3), ctx("en-US"), "short") == "10/3/26"
    assert F.date(date(2026, 10, 3), ctx("fr-FR"), "short") == "03/10/2026"
    assert "€" in F.currency(12.5, "EUR", ctx("fr-FR"))
    assert F.unit(5, "length-kilometer", ctx("en")) == "5 km"


def test_hour_cycle_time_zone_and_week() -> None:
    assert F.time(INSTANT, ctx("en-US", hour_cycle="h23")) == "15:05"
    assert F.time(INSTANT, ctx("fr-FR", hour_cycle="h12")).startswith("3:05")
    assert F.time(INSTANT, ctx("en-US", time_zone="Europe/Paris", hour_cycle="h23")) == "17:05"
    assert F.first_day_of_week(ctx("en-US")) == 6 and F.first_day_of_week(ctx("fr-FR")) == 0
    assert F.first_day_of_week(ctx("fr-FR", first_day_of_week=6)) == 6
    assert "ago" in F.relative(-3600, ctx("en"))


def test_presentation_helpers_keep_values() -> None:
    p = Presentation(F)
    value = 0.4567
    assert p.percentage(value, ctx("en")) == "46%" and value == 0.4567
    assert p.duration(5400, ctx("en")) in ("2 hours", "1.5 hours", "90 minutes")
    assert p.compact(1_250_000, ctx("en")) == "1.2M"
