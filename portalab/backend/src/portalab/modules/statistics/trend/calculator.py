"""``TrendCalculator`` (T028; R10): delta and direction versus the previous period of equal length. An
empty previous period gives no percentage (never a misleading "+∞ %")."""

from typing import Literal

from portalab.capabilities.statistics import Trend

EPSILON = 1e-9


def trend(current: float | None, previous: float | None) -> Trend | None:
    if current is None:
        return None
    before = previous or 0.0
    delta = current - before
    direction: Literal["up", "down", "flat"] = (
        "flat" if abs(delta) < EPSILON else ("up" if delta > 0 else "down")
    )
    percent = None if abs(before) < EPSILON else round(delta / abs(before) * 100, 1)
    return Trend(delta=round(delta, 6), direction=direction, previous_value=before, percent=percent)
