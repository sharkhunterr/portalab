"""Eligibility (T024; R8, FR-004/005): every declared condition must hold (**strict AND**), evaluated
server-side at acquisition; each condition is reported **by name** with whether it is met. A port that is
unavailable (013, 014, 003) fails closed with an explicit ``unavailable`` reason. The Coins price is one
more named condition against the member's balance."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from portalab.capabilities.economy import ECONOMY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.statistics import CAMPAIGNS, PROGRESSION
from portalab.capabilities.user_grants import ROLES_CAPABILITY


@dataclass(frozen=True, slots=True)
class Check:
    name: str  # min_level | achievement | campaign_active | role | coins
    value: Any
    met: bool
    reason: str = ""  # "" | "unmet" | "unavailable"

    def label(self) -> str:
        return f"{self.name}:{self.value}"


class Eligibility:
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    def _port(self, name: str) -> Any | None:
        providers = self.capabilities.system_providers(name)
        return providers[0].provider if providers else None

    async def _one(self, user: UUID, condition: dict[str, Any]) -> Check:
        kind = condition["kind"]
        try:
            if kind == "min_level":
                reader = self._port(PROGRESSION)
                if reader is None:
                    return Check(kind, condition["level"], False, "unavailable")
                ok = await reader.level(user) >= int(condition["level"])
                return Check(kind, condition["level"], ok, "" if ok else "unmet")
            if kind == "achievement":
                reader = self._port(PROGRESSION)
                if reader is None:
                    return Check(kind, condition["achievement"], False, "unavailable")
                ok = await reader.has_achievement(user, condition["achievement"])
                return Check(kind, condition["achievement"], ok, "" if ok else "unmet")
            if kind == "campaign_active":
                reader = self._port(CAMPAIGNS)
                if reader is None:
                    return Check(kind, condition["campaign"], False, "unavailable")
                ok = await reader.is_active(condition["campaign"])
                return Check(kind, condition["campaign"], ok, "" if ok else "unmet")
            if kind == "role":
                reader = self._port(ROLES_CAPABILITY)
                if reader is None:
                    return Check(kind, condition["role"], False, "unavailable")
                ok = condition["role"] in await reader.roles_of(user)
                return Check(kind, condition["role"], ok, "" if ok else "unmet")
        except Exception:
            return Check(
                kind, next(iter(v for k, v in condition.items() if k != "kind"), ""), False, "unavailable"
            )
        return Check(kind, "", False, "unavailable")  # unknown kinds never pass

    async def checks(self, user: UUID, conditions: list[dict[str, Any]], price: int | None) -> list[Check]:
        out = [await self._one(user, c) for c in conditions]
        if price:
            economy = self._port(ECONOMY)
            if economy is None:
                out.append(Check("coins", price, False, "unavailable"))
            else:
                try:
                    ok = await economy.balance(user, "coins") >= price
                    out.append(Check("coins", price, ok, "" if ok else "unmet"))
                except Exception:
                    out.append(Check("coins", price, False, "unavailable"))
        return out
