"""Grant calculator (T016): base amounts per value — fixed, or ``per_unit(field, factor, max)`` on a
rewardable numeric attribute; integer arithmetic, rounded down, never negative."""

import math
from collections.abc import Mapping
from typing import Any

from portalab.modules.gamification.rules.definition import RuleDefinition


def base_amounts(rule: RuleDefinition, payload: Mapping[str, Any]) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for grant in rule.grants:
        if grant.amount is not None:
            amount = grant.amount
        else:
            assert grant.per_unit is not None
            raw = payload.get(grant.per_unit.field)
            if isinstance(raw, bool) or not isinstance(raw, int | float) or raw <= 0:
                continue
            amount = math.floor(raw * grant.per_unit.factor)
            if grant.per_unit.max is not None:
                amount = min(amount, grant.per_unit.max)
        if amount > 0:
            out.append((grant.value, amount))
    return out
