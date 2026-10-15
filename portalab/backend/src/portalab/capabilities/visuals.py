"""Imported visual elements (issue 1, POC): the looks a pack brings from outside Portalab — their animations
in their own files (CSS, GLSL, JS), never in the application's code.

- ``external_looks``: the open vocabulary. The built-in lists (``capabilities.themes``) stay the base; the
  looks of the published packs are added to them at run time, per product type, so a preference or a profile
  slot accepts them like a built-in one.
- ``CatalogWriter`` (provided by Marketplace 015): publishes an element as a shop product — the same path the
  demo catalog takes (created, then revised when its price, texts, contents or level change) — and takes it
  off sale or puts it back.
"""

from collections.abc import Iterable, Mapping
from typing import Any, Protocol, runtime_checkable

from portalab.capabilities.registry import CapabilitySpec
from portalab.capabilities.themes import (
    AMBIENTS,
    AVATAR_FRAMES,
    BADGE_STYLES,
    CELEBRATIONS,
    LEVEL_BADGES,
    LEVEL_UPS,
    NAME_STYLES,
    NOTIFICATION_ANIMATIONS,
    NOTIFICATION_STYLES,
    PALETTES,
    PROFILE_BANNERS,
)
from portalab.core.authz_port import Principal

CATALOG_WRITER = "marketplace.catalog_writer"

# each look type: the product type selling it, the payload field naming the look, its built-in looks
LOOK_TYPES: dict[str, tuple[str, tuple[str, ...]]] = {
    "avatar_frame": ("frame", AVATAR_FRAMES),
    "profile_banner": ("banner", PROFILE_BANNERS),
    "profile_background": ("background", AMBIENTS),
    "name_style": ("style", NAME_STYLES),
    "level_badge": ("style", LEVEL_BADGES),
    "level_up": ("animation", LEVEL_UPS),
    "effect": ("effect", CELEBRATIONS),
    "ambient": ("ambient", AMBIENTS),
    "notification_style": ("style", NOTIFICATION_STYLES),
    "notification_animation": ("animation", NOTIFICATION_ANIMATIONS),
    "palette": ("palette", PALETTES),
    "badge": ("style", BADGE_STYLES),
    "title": ("style", BADGE_STYLES),
}


class ExternalLooks:
    """The looks the published packs add, per product type (replaced as a whole on every change)."""

    def __init__(self) -> None:
        self._by_type: dict[str, tuple[str, ...]] = {}

    def replace(self, by_type: Mapping[str, Iterable[str]]) -> None:
        self._by_type = {kind: tuple(dict.fromkeys(keys)) for kind, keys in by_type.items()}

    def of(self, product_type: str) -> tuple[str, ...]:
        return self._by_type.get(product_type, ())

    def known(self, product_type: str) -> tuple[str, ...]:
        """The built-in looks of this type, then the imported ones."""
        builtin = LOOK_TYPES[product_type][1] if product_type in LOOK_TYPES else ()
        return (*builtin, *(k for k in self.of(product_type) if k not in builtin))


external_looks = ExternalLooks()


@runtime_checkable
class CatalogWriter(Protocol):
    async def publish(self, actor: Principal, product: Mapping[str, Any]) -> str:
        """Creates or revises the product (``created``, ``revised`` or ``unchanged``) and puts it on sale."""
        ...

    async def withdraw(self, actor: Principal, key: str) -> None:
        """Off sale (its owners keep it)."""
        ...


CATALOG_WRITER_SPEC = CapabilitySpec(
    name=CATALOG_WRITER,
    version="1.0",
    protocol=CatalogWriter,
    multi_provider=False,
    description="Publishes shop products defined outside the admin forms — imported visual packs (issue 1)",
)
