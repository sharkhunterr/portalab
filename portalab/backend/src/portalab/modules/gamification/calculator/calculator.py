"""Grant calculator (T016): base amounts per value — fixed, ``per_unit(field, factor, max)`` on a
rewardable numeric attribute, or the fixed part plus the per-unit part (027); integer arithmetic, rounded
down, never negative."""

import math
from collections.abc import Mapping
from typing import Any

from portalab.modules.gamification.rules.definition import RuleDefinition


def base_amounts(rule: RuleDefinition, payload: Mapping[str, Any]) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for grant in rule.grants:
        amount = grant.amount or 0
        if grant.per_unit is not None:
            raw = payload.get(grant.per_unit.field)
            if not isinstance(raw, bool) and isinstance(raw, int | float) and raw > 0:
                extra = math.floor(raw * grant.per_unit.factor)
                if grant.per_unit.max is not None:
                    extra = min(extra, grant.per_unit.max)
                amount += extra
        if amount > 0:
            out.append((grant.value, amount))
    return out


def measured(rule: RuleDefinition, payload: Mapping[str, Any], value: str) -> dict[str, float]:
    """Issue 261: what a grant of ``value`` counted (``watched_s``, ``minutes``…), as the event said it — kept
    with the gain so its journal can say how it was reckoned."""
    out: dict[str, float] = {}
    for grant in rule.grants:
        if grant.value == value and grant.per_unit is not None:
            raw = payload.get(grant.per_unit.field)
            if not isinstance(raw, bool) and isinstance(raw, int | float):
                out[grant.per_unit.field] = round(float(raw), 1)
    return out
