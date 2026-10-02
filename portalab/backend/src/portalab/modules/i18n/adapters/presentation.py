"""Presentation helpers (T036; FR-023..025) for Marketplace, Gamification and Statistics: durations,
percentages, units, compact numbers and catalog-keyed category labels. Pure representation — the stored
values and every business rule stay untouched."""

from typing import Any

from babel.numbers import format_compact_decimal

from portalab.capabilities.i18n import LocaleContext
from portalab.modules.i18n.format.formatter import Formatter, babel_locale


class Presentation:
    def __init__(self, formatter: Formatter | None = None, renderer: Any = None) -> None:
        self.formatter = formatter or Formatter()
        self.renderer = renderer

    def duration(self, seconds: float, ctx: LocaleContext) -> str:
        return self.formatter.duration(seconds, ctx)

    def percentage(self, ratio: float, ctx: LocaleContext) -> str:
        return self.formatter.percent(ratio, ctx)

    def unit(self, value: float, unit: str, ctx: LocaleContext) -> str:
        return self.formatter.unit(value, unit, ctx)

    def compact(self, value: float, ctx: LocaleContext) -> str:
        return str(format_compact_decimal(value, locale=babel_locale(ctx.locale), fraction_digits=1))

    def label(self, namespace: str, key: str, ctx: LocaleContext) -> str:
        return self.renderer.t(key, ctx, namespace=namespace) if self.renderer else key
