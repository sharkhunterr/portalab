"""Visual packs (spec 028, issue 1): the looks packs bring — their animations in their own files (CSS, GLSL,
JS), never in the application's code.

- ``live_looks``: the open vocabulary. The built-in lists (``capabilities.themes``) stay the base until the
  built-in catalog is itself delivered as packs; the looks of the live packs are added to them at run time,
  per element type, so a preference or a profile slot accepts them like a built-in one. Kept by the
  ``visuals`` module from its look claims (every process refreshes it when the registry's epoch moves).
- ``PACK_LOOKS``: while a pack is analysed or published, the looks it brings itself (an interface may wear
  them before they are live).
- ``InterfaceRegistry`` (provided by UI 022): validates an interface definition, registers it, switches it on
  and off — the registry of interfaces stays UI's.
- ``CatalogWriter`` (provided by Marketplace 015): publishes an element as a shop product — the same path the
  demo catalog takes — takes it off sale or puts it back, counts its owners, retires it for good.
"""

from collections.abc import Iterable, Mapping
from contextvars import ContextVar
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
INTERFACE_REGISTRY = "ui.interface_registry"

# the navigations the interface draws itself (an imported interface may bring its own: element ``navigation``)
NAVIGATIONS: tuple[str, ...] = (
    "sidebar", "topbar", "rail", "drawer", "bottom-bar", "orbit", "dock", "tabs", "launcher", "terminal",
    "reel", "lights", "vcr", "sheet", "console", "taskbar", "feed", "player", "masthead", "dpad",
    "planisphere", "system", "deck",
)  # fmt: skip

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
    # not sold on its own — an interface wears it
    "navigation": ("nav", NAVIGATIONS),
}

# while a pack is analysed or published: the (type, look) pairs it brings itself
PACK_LOOKS: ContextVar[frozenset[tuple[str, str]]] = ContextVar("pack_looks", default=frozenset())


class LiveLooks:
    """The looks the live packs add, per element type (replaced as a whole on every change)."""

    def __init__(self) -> None:
        self._by_type: dict[str, tuple[str, ...]] = {}
        self.epoch = -1

    def replace(self, by_type: Mapping[str, Iterable[str]], epoch: int = -1) -> None:
        self._by_type = {kind: tuple(dict.fromkeys(keys)) for kind, keys in by_type.items()}
        self.epoch = epoch

    def of(self, element_type: str) -> tuple[str, ...]:
        return self._by_type.get(element_type, ())

    def known(self, element_type: str) -> tuple[str, ...]:
        """The built-in looks of this type, then the live packs' ones."""
        builtin = LOOK_TYPES[element_type][1] if element_type in LOOK_TYPES else ()
        return (*builtin, *(k for k in self.of(element_type) if k not in builtin))


live_looks = LiveLooks()
external_looks = live_looks  # the proof of concept's name, kept for the modules reading it


@runtime_checkable
class InterfaceRegistry(Protocol):
    def validate(self, document: Mapping[str, Any]) -> tuple[str | None, list[str], dict[str, Any] | None]:
        """``(key, errors, floor report)`` of an interface definition (``key`` ``None`` when invalid); the
        looks it names may be built-in, live, or in ``PACK_LOOKS``."""
        ...

    def builtin_keys(self) -> frozenset[str]:
        """The interfaces Portalab ships (no pack may bring one of the same key)."""
        ...

    async def source_of(self, key: str) -> str | None:
        """Who registered this interface (``visuals:<pack>`` for a pack's), ``None`` when unknown."""
        ...

    async def put(self, actor: Principal, document: Mapping[str, Any], *, source: str) -> None:
        """Registers the interface, or updates its definition when this source registered it."""
        ...

    async def set_enabled(self, actor: Principal, key: str, enabled: bool) -> None: ...


@runtime_checkable
class CatalogWriter(Protocol):
    async def publish(self, actor: Principal, product: Mapping[str, Any]) -> str:
        """Creates or revises the product (``created``, ``revised`` or ``unchanged``) and puts it on sale."""
        ...

    async def withdraw(self, actor: Principal, key: str) -> None:
        """Off sale (its owners keep it)."""
        ...

    async def owners(self, keys: Iterable[str]) -> int:
        """How many live ownerships these products have, together."""
        ...

    async def retire(self, actor: Principal, key: str) -> None:
        """Off sale for good (its pack is removed: the catalog keeps its history)."""
        ...


CATALOG_WRITER_SPEC = CapabilitySpec(
    name=CATALOG_WRITER,
    version="1.1",
    protocol=CatalogWriter,
    multi_provider=False,
    description="Publishes shop products defined outside the admin forms — visual packs (028)",
)

INTERFACE_REGISTRY_SPEC = CapabilitySpec(
    name=INTERFACE_REGISTRY,
    version="1.0",
    protocol=InterfaceRegistry,
    multi_provider=False,
    description="Validates and registers the interfaces visual packs bring (028)",
)
