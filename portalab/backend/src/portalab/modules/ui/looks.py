"""Notification looks (027): the style (shape, layout) and the entrance animation of notifications are a
member's own choice, independent of the theme. The basic ones are free; the others are cosmetics sold in
the Marketplace (product types ``notification_style`` / ``notification_animation``) and chosen by their
owners only — enforced here when the preference is saved, not only hidden in the interface."""

from typing import Any
from uuid import UUID

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import COSMETICS
from portalab.capabilities.visuals import external_looks

FREE_STYLES = frozenset({"theme", "toast", "banner", "pill", "minimal"})
FREE_ANIMATIONS = frozenset({"theme", "slide", "fade", "pop", "zoom"})
KINDS = {
    "ui.notificationStyle": ("notification_style", "style", FREE_STYLES),
    "ui.notificationAnimation": ("notification_animation", "animation", FREE_ANIMATIONS),
    "ui.palette": ("palette", "palette", frozenset({"theme"})),  # 027: colour palettes over the theme
    # 027: animated layer behind the portal and celebration effect (product types ``ambient``/``effect``)
    "ui.ambient": ("ambient", "ambient", frozenset({"theme", "none"})),
    "ui.celebration": ("effect", "effect", frozenset({"theme", "none", "sparkle", "glow"})),
    "ui.levelUp": ("level_up", "animation", frozenset({"theme", "classic"})),  # 027: the level-up moment
}


class NotificationLooks:
    SETTINGS = tuple(KINDS)

    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    def _entitlements(self) -> Any | None:
        try:
            providers = self.capabilities.system_providers(COSMETICS)
        except Exception:
            return None
        return providers[0].provider if providers else None

    async def locked(self, setting: str, user_id: UUID | None) -> frozenset[str]:
        """Choices of ``setting`` the user may not pick (sold, not owned, not free)."""
        kind, field, free = KINDS[setting]
        entitlements = self._entitlements()
        if entitlements is None:
            return frozenset()
        sold = await entitlements.sold(kind, field)
        owned = await entitlements.owned(user_id, kind, field) if user_id else frozenset()
        return frozenset(sold - owned - free)

    async def waiting(self, user_id: UUID | None, kind: str, field: str) -> dict[str, dict[str, int]]:
        """#99: the choices the user won (a booster) but may not pick yet, and what each waits for."""
        entitlements = self._entitlements()
        reader = getattr(entitlements, "waiting", None)
        if reader is None or user_id is None:
            return {}
        try:
            result: dict[str, dict[str, int]] = await reader(user_id, kind, field)
        except Exception:
            return {}
        return result

    async def catalog(self, user_id: UUID | None) -> dict[str, Any]:
        styles = await self.locked("ui.notificationStyle", user_id)
        animations = await self.locked("ui.notificationAnimation", user_id)
        palettes = await self.locked("ui.palette", user_id)
        ambients = await self.locked("ui.ambient", user_id)
        celebrations = await self.locked("ui.celebration", user_id)
        level_ups = await self.locked("ui.levelUp", user_id)

        # #71, #72: each choice comes with the product selling it (its rarity, its price), shown with it
        async def listed(setting: str, keys: tuple[str, ...], locked: frozenset[str]) -> list[dict[str, Any]]:
            kind, field, _ = KINDS[setting]
            sold = await self.details(kind, field)
            waiting = await self.waiting(user_id, kind, field)  # #99: won, waiting for a level
            held = external_looks.held(kind)
            return [
                {
                    "key": k,
                    "locked": k in locked,
                    **sold.get(k, {}),
                    **({"waiting": waiting[k]} if k in waiting else {}),
                }
                # 028: with the looks whose pack is off — to their owners only (« currently unavailable »)
                for k in (*keys, *sorted(held - set(keys)))
                if k not in held or k in waiting
            ]

        return {
            "styles": await listed("ui.notificationStyle", self.choices("ui.notificationStyle"), styles),
            "animations": await listed(
                "ui.notificationAnimation", self.choices("ui.notificationAnimation"), animations
            ),
            "palettes": await listed("ui.palette", self.choices("ui.palette"), palettes),
            "ambients": await listed("ui.ambient", self.choices("ui.ambient"), ambients),
            "celebrations": await listed("ui.celebration", self.choices("ui.celebration"), celebrations),
            "level_ups": await listed("ui.levelUp", self.choices("ui.levelUp"), level_ups),
        }

    async def details(self, kind: str, field: str) -> dict[str, dict[str, Any]]:
        """The product selling each choice (key, rarity, price), when the Marketplace says (#71)."""
        entitlements = self._entitlements()
        details = getattr(entitlements, "details", None)
        if details is None:
            return {}
        try:
            result: dict[str, dict[str, Any]] = await details(kind, field)
        except Exception:
            return {}
        return result

    @staticmethod
    def choices(setting: str) -> tuple[str, ...]:
        """issue 1: the built-in looks of this setting, then those of the published packs."""
        kind, _, _ = KINDS[setting]
        return external_looks.known(kind)

    def validator(self, setting: str) -> Any:
        async def errors(value: Any, user_ref: str | None = None) -> list[str]:
            if value is None:
                return []
            _, _, free = KINDS[setting]
            if value != "theme" and value not in free and value not in self.choices(setting):
                return [f"{value!r} is not a known look"]
            try:
                user = UUID(user_ref) if user_ref else None
            except ValueError:
                user = None
            if value in await self.locked(setting, user):
                return [f"{value!r} is sold in the shop: buy it to use it"]
            return []

        return errors
