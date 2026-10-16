"""``ui.theme_catalog`` (spec 022, consumed by Campaigns 014): the theme keys that exist and the Admin
policy currently allows — campaigns may only name such a theme as an overlay."""

from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

CAPABILITY = "ui.theme_catalog"
ENTITLEMENTS = "marketplace.theme_entitlements"


@runtime_checkable
class ThemeCatalog(Protocol):
    async def allowed_keys(self) -> frozenset[str]: ...


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=ThemeCatalog,
    multi_provider=False,
    description="Theme keys enabled and allowed by policy (022)",
)


@runtime_checkable
class ThemeEntitlements(Protocol):
    """027 US11 (provided by Marketplace 015): a theme sold as a product is chosen by its owners only."""

    async def sold(self) -> frozenset[str]:
        """Theme keys offered by an available ``theme`` product."""
        ...

    async def owned(self, user_id: UUID) -> frozenset[str]:
        """Theme keys of the ``theme`` products the user owns (live ownerships)."""
        ...


ENTITLEMENTS_SPEC = CapabilitySpec(
    name=ENTITLEMENTS,
    version="1.0",
    protocol=ThemeEntitlements,
    multi_provider=False,
    description="Themes sold in the Marketplace and the ones a user owns (027 US11)",
)


COSMETICS = "marketplace.cosmetics"

# 027 / 028: profile and colour cosmetics — none is listed here: their looks are what the visual packs hold
# (Portalab's own packs included), the open vocabulary of ``capabilities.visuals.live_looks``; a design no
# product sells is free for everyone.

PROFILE_SLOTS = {
    "banner": ("profile_banner", "banner"),
    "frame": ("avatar_frame", "frame"),
    "background": ("profile_background", "background"),
    "name": ("name_style", "style"),
    "level": ("level_badge", "style"),  # 027: the level badge's look, worn on the profile
}


@runtime_checkable
class CosmeticEntitlements(Protocol):
    """027 (provided by Marketplace 015): cosmetic choices sold as products — notification styles and
    animations… — are chosen by their owners only. ``kind`` is the product type, ``field`` the payload key
    naming the choice (e.g. ``notification_style`` / ``style``)."""

    async def sold(self, kind: str, field: str) -> frozenset[str]: ...

    async def owned(self, user_id: UUID, kind: str, field: str) -> frozenset[str]: ...

    async def equipped(self, user_id: UUID) -> dict[str, Any]:
        """The profile cosmetics a member wears: ``banner``, ``frame``, ``backdrop`` ({object_id, ref})."""
        ...


COSMETICS_SPEC = CapabilitySpec(
    name=COSMETICS,
    version="1.0",
    protocol=CosmeticEntitlements,
    multi_provider=False,
    description="Cosmetic choices sold in the Marketplace and the ones a user owns (027)",
)
