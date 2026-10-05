"""Notification looks (027): the style (shape, layout) and the entrance animation of notifications are a
member's own choice, independent of the theme. The basic ones are free; the others are cosmetics sold in
the Marketplace (product types ``notification_style`` / ``notification_animation``) and chosen by their
owners only — enforced here when the preference is saved, not only hidden in the interface."""

from typing import Any
from uuid import UUID

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import (
    AMBIENTS,
    CELEBRATIONS,
    COSMETICS,
    NOTIFICATION_ANIMATIONS,
    NOTIFICATION_STYLES,
    PALETTES,
)

STYLES = NOTIFICATION_STYLES
ANIMATIONS = NOTIFICATION_ANIMATIONS
FREE_STYLES = frozenset({"theme", "toast", "banner", "pill", "minimal"})
FREE_ANIMATIONS = frozenset({"theme", "slide", "fade", "pop", "zoom"})
KINDS = {
    "ui.notificationStyle": ("notification_style", "style", FREE_STYLES),
    "ui.notificationAnimation": ("notification_animation", "animation", FREE_ANIMATIONS),
    "ui.palette": ("palette", "palette", frozenset({"theme"})),  # 027: colour palettes over the theme
    # 027: animated layer behind the portal and celebration effect (product types ``ambient``/``effect``)
    "ui.ambient": ("ambient", "ambient", frozenset({"theme", "none"})),
    "ui.celebration": ("effect", "effect", frozenset({"theme", "none", "sparkle", "glow"})),
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

    async def catalog(self, user_id: UUID | None) -> dict[str, Any]:
        styles = await self.locked("ui.notificationStyle", user_id)
        animations = await self.locked("ui.notificationAnimation", user_id)
        palettes = await self.locked("ui.palette", user_id)
        ambients = await self.locked("ui.ambient", user_id)
        celebrations = await self.locked("ui.celebration", user_id)
        return {
            "styles": [{"key": k, "locked": k in styles} for k in STYLES],
            "animations": [{"key": k, "locked": k in animations} for k in ANIMATIONS],
            "palettes": [{"key": k, "locked": k in palettes} for k in PALETTES],
            "ambients": [{"key": k, "locked": k in ambients} for k in AMBIENTS],
            "celebrations": [{"key": k, "locked": k in celebrations} for k in CELEBRATIONS],
        }

    def validator(self, setting: str) -> Any:
        async def errors(value: Any, user_ref: str | None = None) -> list[str]:
            if value is None:
                return []
            try:
                user = UUID(user_ref) if user_ref else None
            except ValueError:
                user = None
            if value in await self.locked(setting, user):
                return [f"{value!r} is sold in the shop: buy it to use it"]
            return []

        return errors
