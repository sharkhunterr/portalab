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

# 027: profile and colour cosmetics — designs drawn by the interface (no image file), keys shared by the
# Marketplace (what is sold) and the UI (what is shown). A design no product sells is free for everyone.
PROFILE_BANNERS: tuple[str, ...] = (
    "aurora", "ocean", "dusk", "forest", "sunset", "synthwave", "starfield", "sakura", "circuit", "halloween",
    # 027 universes
    "castle", "hyperspace", "code", "dunes", "bloodmoon", "snowfall", "pow", "speedlines", "toon", "cabin",
    "neon-grid", "mono", "nebula", "skyline", "mirrorball", "night-city",
)  # fmt: skip
AVATAR_FRAMES: tuple[str, ...] = (
    "none", "simple", "gold", "neon", "flames", "frost", "rainbow", "pixel",
    "runes", "orbit", "code", "sand", "blood", "pumpkin", "holly", "pow", "chrome", "hologram", "cyber",
    "hero", "disco", "toxic", "sakura",
)  # fmt: skip
PALETTES: tuple[str, ...] = (
    "theme", "ocean", "forest", "sunset", "candy", "royal", "ember", "matrix",
    "aurora", "lagoon", "lava", "mint", "gold", "ice", "rose", "toxic", "midnight", "coffee", "lavender",
    "bubblegum", "polar", "copper", "solar", "berry", "slate", "peach", "crimson",
)  # fmt: skip
# animated layers: behind the whole portal (ambient preference, theme default) or a profile (background)
AMBIENTS: tuple[str, ...] = (
    "none", "snow", "embers", "code-rain", "fireflies", "starfield", "warp", "petals", "bats", "bubbles",
    "rain", "sparkles", "disco", "fog", "sand", "leaves", "hearts", "glitch", "lights", "spores", "aurora",
)  # fmt: skip
CELEBRATIONS: tuple[str, ...] = (
    "none", "sparkle", "confetti", "glow", "snow", "bats", "pixels", "hearts", "stars", "coins", "lightning",
    "petals", "bubbles", "assemble", "burn", "shatter", "freeze", "glitch", "portal",
)  # fmt: skip
NOTIFICATION_STYLES: tuple[str, ...] = (
    "toast", "banner", "pill", "minimal", "glass", "neon", "comic", "terminal", "parchment", "hologram",
    "pixel", "paper", "square", "circle", "cloud", "ticket", "tag", "split",
)  # fmt: skip
NOTIFICATION_ANIMATIONS: tuple[str, ...] = (
    "slide", "fade", "pop", "zoom", "bounce", "flip", "swing", "glitch", "drop", "spiral", "slam",
    "rise", "wipe", "focus", "jelly", "shake",
)  # fmt: skip
# the name shown big on a profile: a font and an effect (Steam-like « titles »)
NAME_STYLES: tuple[str, ...] = (
    "none", "wizard", "galaxy", "matrix", "desert", "horror", "halloween", "christmas", "comic", "manga",
    "cartoon", "cozy", "futuristic", "minimal", "alien", "hero", "neowave", "disco", "cyberpunk", "pixel",
    "handwritten", "fire", "ice", "rainbow", "royal",
)  # fmt: skip
# animated badges and titles (payload ``style`` of ``badge``/``title`` products)
BADGE_STYLES: tuple[str, ...] = (
    "none", "shimmer", "pulse", "flame", "glitch", "rainbow", "float", "spin", "frost", "neon", "gold",
)  # fmt: skip
UNIVERSE_THEMES: tuple[str, ...] = (
    "wizard", "galaxy", "matrix", "desert", "horror", "halloween", "christmas", "comic", "manga", "cartoon",
    "cozy", "futuristic", "minimal", "alien", "heroes", "neowave", "disco", "cyberpunk",
)  # fmt: skip
PROFILE_SLOTS = {
    "banner": ("profile_banner", "banner"),
    "frame": ("avatar_frame", "frame"),
    "background": ("profile_background", "background"),
    "name": ("name_style", "style"),
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
