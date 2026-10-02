"""CLDR formatting (T021; R4, FR-005..007) with Babel: numbers, percentages, currency display, units,
dates/times (honouring the user's hour cycle), relative time and first day of the week — always from the
*locale*, never the interface language, and never altering stored values."""

from datetime import date, datetime, timedelta
from typing import Any, Literal

from babel import Locale, UnknownLocaleError
from babel.dates import format_date, format_datetime, format_time, format_timedelta, get_timezone
from babel.numbers import format_currency, format_decimal, format_percent, get_decimal_symbol
from babel.units import format_unit

from portalab.capabilities.i18n import LocaleContext


def babel_locale(code: str) -> Locale:
    try:
        return Locale.parse(code.replace("-", "_"))
    except (UnknownLocaleError, ValueError):
        return Locale.parse("en")


def babel_decimal(locale: Locale) -> str:
    return str(get_decimal_symbol(locale))


class Formatter:
    def number(self, value: float, ctx: LocaleContext) -> str:
        return str(format_decimal(value, locale=babel_locale(ctx.locale)))

    def percent(self, ratio: float, ctx: LocaleContext) -> str:
        return str(format_percent(ratio, locale=babel_locale(ctx.locale)))

    def currency(self, amount: float, currency: str, ctx: LocaleContext) -> str:
        return str(format_currency(amount, currency, locale=babel_locale(ctx.locale)))

    def unit(
        self,
        value: float,
        unit: str,
        ctx: LocaleContext,
        length: Literal["short", "long", "narrow"] = "short",
    ) -> str:
        return str(format_unit(value, unit, length=length, locale=babel_locale(ctx.locale)))

    def date(self, value: date | datetime, ctx: LocaleContext, style: str = "medium") -> str:
        if isinstance(value, datetime):
            value = value.astimezone(get_timezone(ctx.time_zone)).date()
        return str(format_date(value, format=style, locale=babel_locale(ctx.locale)))

    def time(self, value: datetime, ctx: LocaleContext, style: str = "short") -> str:
        locale = babel_locale(ctx.locale)
        tz = get_timezone(ctx.time_zone)
        if ctx.hour_cycle == "h23":
            return str(format_time(value, format="HH:mm", tzinfo=tz, locale=locale))
        if ctx.hour_cycle == "h12":
            return str(format_time(value, format="h:mm a", tzinfo=tz, locale=locale))
        return str(format_time(value, format=style, tzinfo=tz, locale=locale))

    def datetime(self, value: datetime, ctx: LocaleContext, style: str = "medium") -> str:
        if ctx.hour_cycle:
            return f"{self.date(value, ctx, style)} {self.time(value, ctx)}"
        return str(
            format_datetime(
                value, format=style, tzinfo=get_timezone(ctx.time_zone), locale=babel_locale(ctx.locale)
            )
        )

    def relative(self, seconds: float, ctx: LocaleContext) -> str:
        return str(
            format_timedelta(
                timedelta(seconds=seconds), add_direction=True, threshold=0.9, locale=babel_locale(ctx.locale)
            )
        )

    def duration(self, seconds: float, ctx: LocaleContext) -> str:
        return str(
            format_timedelta(timedelta(seconds=seconds), threshold=0.9, locale=babel_locale(ctx.locale))
        )

    def first_day_of_week(self, ctx: LocaleContext) -> int:
        if ctx.first_day_of_week is not None:
            return ctx.first_day_of_week
        return int(babel_locale(ctx.locale).first_week_day)

    def describe(self, ctx: LocaleContext) -> dict[str, Any]:
        locale = babel_locale(ctx.locale)
        return {
            "decimal": str(babel_decimal(locale)),
            "first_day_of_week": self.first_day_of_week(ctx),
        }
