"""Rule simulation (T014; R14): dry-runs a rule definition against sample events — base amounts, the
applied modifiers and the cap — and **writes nothing**. Anti-abuse windows are not consumed."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from portalab.capabilities.events import EventTypeRegistry
from portalab.modules.gamification.calculator.calculator import base_amounts
from portalab.modules.gamification.modifiers.combiner import ModifierCombiner
from portalab.modules.gamification.rules.definition import matches, parse_rule


async def simulate(
    raw: Mapping[str, Any],
    samples: Sequence[Mapping[str, Any]],
    *,
    types: EventTypeRegistry,
    combiner: ModifierCombiner,
    cap: float,
    user: UUID,
    now: datetime,
) -> list[dict[str, Any]]:
    rule = parse_rule(raw, types)
    results: list[dict[str, Any]] = []
    for index, sample in enumerate(samples[:50]):
        payload = dict(sample.get("payload") or {})
        at = sample.get("occurred_at") or now
        if isinstance(at, str):
            at = datetime.fromisoformat(at)
        if not matches(rule.predicate, payload):
            results.append({"sample": index, "matched": False, "grants": []})
            continue
        grants = []
        for value, base in base_amounts(rule, payload):
            combined = await combiner.combined(user, rule.event_type, value, at, rule.multiplier, cap)  # type: ignore[arg-type]
            grants.append(
                {
                    "value": value,
                    "base": base,
                    "amount": combined.apply(base),
                    "factor": round(combined.factor, 4),
                }
                | combined.record()
            )
        results.append({"sample": index, "matched": True, "grants": grants})
    return results
