"""013 T018 — modifiers multiply (x2 · x1.5 = x3, CD-024), the product is capped by
``economy.maxTotalBoost`` and recorded; deterministic order; validity by ``occurred_at`` belongs to the
provider; an unavailable provider leaves the rule multiplier only (flagged), never blocking the grant."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.economy import MODIFIERS, Modifier, ModifierProvider
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.gamification.modifiers.combiner import ModifierCombiner, combine

AT = datetime(2026, 10, 1, 12, tzinfo=UTC)
EVENT = object()  # providers receive the occurrence; these fakes only look at the instant


def test_multiplicative_and_capped() -> None:
    combined = combine(1.5, [Modifier("campaign:b", 2.0)], cap=5.0)
    assert combined.factor == 3.0 and combined.apply(20) == 60 and not combined.capped
    capped = combine(2.0, [Modifier("campaign:b", 2.0), Modifier("campaign:a", 3.0)], cap=5.0)
    assert capped.factor == 5.0 and capped.capped and capped.apply(10) == 50
    assert [m["source_ref"] for m in capped.applied] == ["rule", "campaign:a", "campaign:b"]
    assert capped.record()["capped"] is True
    assert combine(1.0, [Modifier("campaign:x", 0.0)], cap=5.0).factor == 1.0


class Window:
    def __init__(self, start: datetime, end: datetime) -> None:
        self.start, self.end = start, end

    async def modifiers_for(
        self, user: UUID, event_type: str, value: str, at: datetime
    ) -> Sequence[Modifier]:
        return [Modifier("campaign:week", 2.0)] if self.start <= at < self.end else []


class Broken:
    async def modifiers_for(
        self, user: UUID, event_type: str, value: str, at: datetime
    ) -> Sequence[Modifier]:
        raise RuntimeError("campaigns down")


def registry(*providers: object) -> CapabilityRegistry:
    caps = new_registry()
    for index, provider in enumerate(providers):
        assert isinstance(provider, ModifierProvider)
        caps.provide(MODIFIERS, provider, instance_ref=f"p{index}", owner="module:campaigns")
    return caps


async def test_provider_window_and_failure() -> None:
    user = uuid4()
    window = Window(AT, AT.replace(hour=13))
    combiner = ModifierCombiner(registry(window))
    inside = await combiner.combined(user, EVENT, "xp", AT, 1.5, 5.0)  # type: ignore[arg-type]
    outside = await combiner.combined(user, EVENT, "xp", AT.replace(hour=14), 1.5, 5.0)  # type: ignore[arg-type]
    assert inside.factor == 3.0 and outside.factor == 1.5
    degraded = await ModifierCombiner(registry(Broken())).combined(user, EVENT, "xp", AT, 1.5, 5.0)  # type: ignore[arg-type]
    assert degraded.factor == 1.5 and degraded.unavailable and degraded.apply(10) == 15
