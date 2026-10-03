"""Achievements view (T020; US4, slice C): definitions and rewards come from 013 (``economy.catalog``), never
re-defined here. The viewer's own view shows locked, unlocked and hidden achievements (a hidden one reveals
nothing until unlocked); another member's view lists **unlocked** achievements only, and only when that
member's ``progression`` visibility lets this viewer see it (absent otherwise, like a missing member)."""

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from portalab.capabilities.economy import CATALOG
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.visibility_port import VisibilityFilter
from portalab.modules.community.observability import log, metrics
from portalab.modules.community.preferences import shown

PROGRESSION = "progression"
State = Literal["available", "no-data", "unavailable"]
SHOWN_FIELDS = ("key", "state", "label", "description", "icon", "unlocked_at", "progress")


@dataclass(frozen=True, slots=True)
class CatalogView:
    state: State
    items: list[dict[str, Any]] = field(default_factory=list)


def catalog(capabilities: CapabilityRegistry) -> Any | None:
    providers = capabilities.system_providers(CATALOG)
    return providers[0].provider if providers else None


class AchievementsView:
    def __init__(self, capabilities: CapabilityRegistry, visibility: VisibilityFilter) -> None:
        self.capabilities = capabilities
        self.visibility = visibility

    async def mine(self, viewer: Principal) -> CatalogView:
        user = viewer.acting_for or viewer.user_id
        source = catalog(self.capabilities)
        if user is None or source is None:
            return CatalogView("unavailable")
        try:
            raw = await source.achievements_of(user)
        except Exception as error:
            metrics.increment("community.achievements.unavailable")
            log.warning("achievements unavailable", extra={"error": type(error).__name__})
            return CatalogView("unavailable")
        items = []
        for item in raw:
            if item.get("state") == "hidden":
                items.append({"key": item.get("key"), "state": "hidden"})  # nothing else until unlocked
            else:
                items.append({k: item.get(k) for k in SHOWN_FIELDS})
        return CatalogView("available" if items else "no-data", items)

    async def of(self, viewer: Principal, member: UUID) -> CatalogView | None:
        """``None`` when the member's progression is not visible to this viewer."""
        if not await shown(self.visibility, viewer, member, PROGRESSION, True):
            return None
        source = catalog(self.capabilities)
        if source is None:
            return CatalogView("unavailable")
        try:
            raw = await source.unlocked_of(member, 50)
        except Exception:
            metrics.increment("community.achievements.unavailable")
            return CatalogView("unavailable")
        items = [
            {
                "key": i.get("key"),
                "state": "unlocked",
                "label": i.get("label"),
                "unlocked_at": i.get("unlocked_at"),
            }
            for i in raw
        ]
        return CatalogView("available" if items else "no-data", items)
