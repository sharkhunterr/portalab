"""#54/#55 — the shop's perk types hand their payload to Gamification's ``economy.perks``, keyed by the
ownership (idempotent), and refuse an invalid boost."""

from collections.abc import Sequence
from uuid import UUID, uuid4

from portalab.capabilities.economy import PERKS, SPECS
from portalab.capabilities.marketplace import OwnershipView
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.marketplace.types.registry import NOT_REFUNDABLE, BoostHandler, StreakFreezeHandler


class _Perks:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def grant_freezes(self, user: UUID, count: int, source: str) -> None:
        self.calls.append(("freeze", count, source))

    async def grant_boost(
        self, user: UUID, factor: float, hours: float, values: Sequence[str], source: str
    ) -> None:
        self.calls.append(("boost", factor, hours, list(values), source))


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
