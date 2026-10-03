"""Modifier combination (T019; CD-024): ``final = base · Π(rule multiplier, campaign modifiers)``, the
product capped at ``economy.maxTotalBoost``; deterministic order (by source); a failing provider leaves
only the rule multiplier (recorded ``modifiers_unavailable``) and never blocks the base grant."""

import asyncio
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from portalab.capabilities.economy import MODIFIERS, Modifier, Value
from portalab.capabilities.events import Envelope
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.gamification.observability import log, metrics

PROVIDER_TIMEOUT = 2.0


@dataclass(frozen=True, slots=True)
class Combined:
    factor: float
    applied: list[dict[str, Any]] = field(default_factory=list)
    capped: bool = False
    unavailable: bool = False

    def apply(self, base: int) -> int:
        return max(0, math.floor(base * self.factor + 1e-9))

    def record(self) -> dict[str, Any]:
        return {"applied": self.applied, "capped": self.capped, "modifiers_unavailable": self.unavailable}


def combine(
    rule_multiplier: float, modifiers: Sequence[Modifier], cap: float, *, unavailable: bool = False
) -> Combined:
    applied = [{"source_ref": "rule", "factor": rule_multiplier}]
    product = rule_multiplier
    for modifier in sorted(modifiers, key=lambda m: (m.source_ref, m.factor)):
        if modifier.factor <= 0:
            continue
        applied.append({"source_ref": modifier.source_ref, "factor": modifier.factor})
        product *= modifier.factor
    capped = product > cap
    return Combined(min(product, cap), applied, capped, unavailable)


class ModifierCombiner:
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def modifiers(
        self, user: UUID, event: Envelope, value: Value, at: datetime
    ) -> tuple[list[Modifier], bool]:
        try:
            providers = self.capabilities.system_providers(MODIFIERS)
        except Exception:
            return [], False
        found: list[Modifier] = []
        unavailable = False
        for registration in providers:
            try:
                found.extend(
                    await asyncio.wait_for(
                        registration.provider.modifiers_for(user, event, value, at), PROVIDER_TIMEOUT
                    )
                )
            except Exception:
                unavailable = True
                metrics.increment("gamification.modifiers.unavailable")
                log.warning(
                    "modifier provider unavailable", extra={"fields": {"provider": registration.instance_ref}}
                )
        return found, unavailable

    async def combined(
        self, user: UUID, event: Envelope, value: Value, at: datetime, rule_multiplier: float, cap: float
    ) -> Combined:
        found, unavailable = await self.modifiers(user, event, value, at)
        return combine(rule_multiplier, found, cap, unavailable=unavailable)
