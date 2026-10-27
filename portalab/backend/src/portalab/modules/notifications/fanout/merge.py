"""Issue 258: what a series of repeats merged into one notification brought in all — the rewards they name
(XP, the site's currency, contribution) added up, the other parameters the latest's — issue 261: the
minutes counted added up too, and the work a gain was about left unsaid when the series is about several."""

from collections.abc import Mapping
from typing import Any

REWARD_VALUES = ("xp", "coins", "contribution")
COUNTS = ("minutes",)


def rewards_of(params: Mapping[str, Any]) -> dict[str, float]:
    """The rewards a communication names: one per value (``xp``, ``coins``…), or its ``value`` and
    ``amount``."""
    named = {
        value: float(params[value])
        for value in REWARD_VALUES
        if isinstance(params.get(value), int | float) and not isinstance(params.get(value), bool)
    }
    if not named and params.get("value") in REWARD_VALUES:
        amount = params.get("amount")
        if isinstance(amount, int | float) and not isinstance(amount, bool):
            named = {str(params["value"]): float(amount)}
    return named


def merged(before: Mapping[str, Any], latest: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(latest)
    old, new = rewards_of(before), rewards_of(latest)
    for value in REWARD_VALUES:
        if value in old or value in new:
            total = old.get(value, 0.0) + new.get(value, 0.0)
            out[value] = int(total) if total.is_integer() else total
    for key in COUNTS:
        a, b = before.get(key), latest.get(key)
        if isinstance(a, int | float) and isinstance(b, int | float) and _number(a) and _number(b):
            out[key] = a + b
    if "work" in before and before.get("work") != latest.get("work"):
        out["work"] = "none"
    return out


def _number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
