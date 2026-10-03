"""015 T022 — eligibility: free/Coins/min level/achievement/campaign/role conditions combined with strict
AND; unmet conditions returned by name; ports unavailable ⇒ fail closed with an explicit reason."""

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4

from portalab.capabilities.economy import ECONOMY
from portalab.capabilities.statistics import CAMPAIGNS, PROGRESSION
from portalab.capabilities.user_grants import ROLES_CAPABILITY
from portalab.modules.marketplace.eligibility.service import Eligibility

USER = uuid4()
CONDITIONS = [
    {"kind": "min_level", "level": 3},
    {"kind": "achievement", "achievement": "first-steps"},
    {"kind": "campaign_active", "campaign": "halloween"},
    {"kind": "role", "role": "vip"},
]


@dataclass
class World:
    level: int = 3
    achievement: bool = True
    campaign: bool = True
    roles: frozenset[str] = frozenset({"user", "vip"})
    coins: int = 100

    async def has_achievement(self, user_id: UUID, achievement: str) -> bool:
        return self.achievement

    async def is_active(self, campaign: str) -> bool:
        return self.campaign

    async def roles_of(self, user_id: UUID) -> frozenset[str]:
        return self.roles

    async def balance(self, user: UUID, value: str) -> int:
        return self.coins


class Progression:
    def __init__(self, world: World) -> None:
        self.world = world

    async def level(self, user_id: UUID) -> int:
        return self.world.level

    async def has_achievement(self, user_id: UUID, achievement: str) -> bool:
        return self.world.achievement


class Ports:
    """Only what Eligibility reads: ``system_providers(name)``."""

    def __init__(self, world: World | None) -> None:
        self.providers: dict[str, object] = {}
        if world is not None:
            self.providers = {
                PROGRESSION: Progression(world),
                CAMPAIGNS: world,
                ROLES_CAPABILITY: world,
                ECONOMY: world,
            }

    def system_providers(self, name: str) -> list[SimpleNamespace]:
        return [SimpleNamespace(provider=self.providers[name])] if name in self.providers else []


async def checks(world: World | None, price: int | None = 50) -> dict[str, tuple[bool, str]]:
    result = await Eligibility(Ports(world)).checks(USER, CONDITIONS, price)  # type: ignore[arg-type]
    return {c.label(): (c.met, c.reason) for c in result}


async def test_all_conditions_must_hold() -> None:
    assert all(met for met, _ in (await checks(World())).values())
    unmet = await checks(World(level=2, campaign=False, coins=10))
    assert {k for k, (met, _) in unmet.items() if not met} == {
        "min_level:3",
        "campaign_active:halloween",
        "coins:50",
    }
    assert unmet["min_level:3"] == (False, "unmet")
    free = await checks(World(), price=None)
    assert "coins:None" not in free and len(free) == 4


async def test_unavailable_ports_fail_closed() -> None:
    result = await checks(None)
    assert all(not met and reason == "unavailable" for met, reason in result.values())
