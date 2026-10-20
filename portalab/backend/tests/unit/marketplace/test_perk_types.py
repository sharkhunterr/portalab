"""#54/#55/#57 — the shop's perk types hand their payload to Gamification's ``economy.perks``, keyed by the
ownership (idempotent), and refuse an invalid boost."""

from collections.abc import Sequence
from uuid import UUID, uuid4

from portalab.capabilities.economy import PERKS, SPECS
from portalab.capabilities.marketplace import OwnershipView
from portalab.capabilities.media_core import RESCUES
from portalab.capabilities.media_core import SPECS as MEDIA_SPECS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.marketplace.types.registry import (
    NOT_REFUNDABLE,
    BoostHandler,
    RescueHandler,
    StreakFreezeHandler,
)


class _Perks:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def grant_freezes(self, user: UUID, count: int, source: str) -> None:
        self.calls.append(("freeze", count, source))

    async def grant_boost(
        self, user: UUID, factor: float, hours: float, values: Sequence[str], source: str
    ) -> None:
        self.calls.append(("boost", factor, hours, list(values), source))

    async def credit_coins(self, user: UUID, amount: int, source: str, idempotency_key: str) -> None:
        self.calls.append(("coins", amount, source))


def _registry(perks: _Perks | None) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.declare(next(spec for spec in SPECS if spec.name == PERKS))
    if perks is not None:
        registry.provide(PERKS, perks, instance_ref="gamification", owner="test")
    return registry


def _owned(kind: str, payload: dict[str, object]) -> OwnershipView:
    return OwnershipView(uuid4(), uuid4(), f"{kind}_x", kind, payload)


async def test_perks_are_granted_once_per_ownership() -> None:
    perks = _Perks()
    registry = _registry(perks)
    freeze = _owned("streak_freeze", {"count": 3})
    assert (await StreakFreezeHandler(registry).activate(freeze)).state == "active"
    boost = _owned("xp_boost", {"factor": 1.5, "hours": 24, "values": ["xp", "contribution"]})
    assert (await BoostHandler(registry).activate(boost)).state == "active"
    assert perks.calls == [
        ("freeze", 3, f"marketplace:{freeze.id}"),
        ("boost", 1.5, 24.0, ["xp"], f"marketplace:{boost.id}"),  # contribution is never boosted
    ]
    assert {"streak_freeze", "xp_boost"} <= NOT_REFUNDABLE


async def test_invalid_perks_are_refused() -> None:
    perks = _Perks()
    registry = _registry(perks)
    for payload in ({"factor": 1, "hours": 24}, {"factor": 2, "hours": 0}, {"factor": "x", "hours": 1}):
        assert (await BoostHandler(registry).activate(_owned("xp_boost", payload))).state == "incompatible"
    assert (await StreakFreezeHandler(registry).activate(_owned("streak_freeze", {"count": 0}))).state == (
        "incompatible"
    )
    assert (
        await BoostHandler(_registry(None)).activate(_owned("xp_boost", {"factor": 2, "hours": 1}))
    ).state == ("failed")
    assert perks.calls == []


async def test_rescues_are_credited_to_media() -> None:
    """#57: a rescue bought in the shop is credited to Media (keyed by the ownership); not refundable."""
    granted: list[tuple[int, str]] = []

    class _Rescues:
        async def grant(self, user: UUID, count: int, source_ref: str) -> int:
            granted.append((count, source_ref))
            return count

    registry = CapabilityRegistry()
    registry.declare(next(spec for spec in MEDIA_SPECS if spec.name == RESCUES))
    assert (await RescueHandler(registry).activate(_owned("media_rescue", {"count": 1}))).state == "failed"
    registry.provide(RESCUES, _Rescues(), instance_ref="media", owner="test")
    rescue = _owned("media_rescue", {"count": 3})
    assert (await RescueHandler(registry).activate(rescue)).state == "active"
    assert (await RescueHandler(registry).activate(_owned("media_rescue", {"count": 0}))).state == (
        "incompatible"
    )
    assert granted == [(3, f"marketplace:{rescue.id}")] and "media_rescue" in NOT_REFUNDABLE


async def test_assistant_capacities_go_to_the_assistant() -> None:
    """Issue 173: a capacity of the assistant is handed to ``ai.perks`` (keyed by the ownership), one the
    portal does not offer is « incompatible », a revoke withdraws it; not refundable."""
    from portalab.capabilities.ai import PERKS as AI_PERKS
    from portalab.capabilities.ai import SPECS as AI_SPECS
    from portalab.modules.marketplace.types.registry import AiCapacityHandler

    granted: list[tuple[str, int, int, str]] = []
    revoked: list[str] = []

    class _AiPerks:
        async def grant(self, user: UUID, perk: str, amount: int, hours: int, source_ref: str) -> bool:
            granted.append((perk, amount, hours, source_ref))
            return perk != "unknown"

        async def revoke(self, source_ref: str) -> None:
            revoked.append(source_ref)

    registry = CapabilityRegistry()
    registry.declare(next(spec for spec in AI_SPECS if spec.name == AI_PERKS))
    handler = AiCapacityHandler(registry)
    tokens = _owned("ai_capacity", {"perk": "daily_tokens", "amount": 20000, "hours": 168})
    assert (await handler.activate(tokens)).state == "failed"  # no assistant: nothing granted
    registry.provide(AI_PERKS, _AiPerks(), instance_ref="ai", owner="test")
    assert (await handler.activate(tokens)).state == "active"
    assert (await handler.activate(_owned("ai_capacity", {"perk": "unknown"}))).state == "incompatible"
    await handler.deactivate(tokens)
    assert granted[0] == ("daily_tokens", 20000, 168, f"marketplace:{tokens.id}")
    assert revoked == [f"marketplace:{tokens.id}"] and "ai_capacity" in NOT_REFUNDABLE
