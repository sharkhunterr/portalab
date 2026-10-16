"""Visual packs (spec 028, issue 1): the looks packs bring — their animations in their own files (CSS, GLSL,
JS), never in the application's code.

- ``live_looks``: the open vocabulary — nothing of it is written in the code. Its base is what Portalab's own
  packs hold (``ship``: read from the packs shipped with the release, switched on or not, by every process
  at start — even ``portalab migrate``, before any database read); the looks of the live packs are added at
  run time, per element type, so a preference or a profile slot accepts them like Portalab's own. Kept by
  the ``visuals`` module from its look claims (every process refreshes it when the registry's epoch moves).
- ``PACK_LOOKS``: while a pack is analysed or published, the looks it brings itself (an interface may wear
  them before they are live).
- ``InterfaceRegistry`` (provided by UI 022): validates an interface definition, registers it, switches it on
  and off — the registry of interfaces stays UI's.
- ``CatalogWriter`` (provided by Marketplace 015): publishes an element as a shop product — the same path the
  demo catalog takes — takes it off sale or puts it back, counts its owners, retires it for good.
- ``WIDGET_CONTRACTS``: the data a pack's widget may ask for (R26). The widget never calls the portal: the
  member's own page reads each contract through the portal's usual routes (the member's session, the member's
  permissions) and hands the widget only the contract's fields; any dashboard widget's data is a contract too
  (``widget:<key>``). The analysis refuses any other contract and the administrator accepts each one at the
  Review step.
"""

import json
import os
import re
from collections.abc import Iterable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

CATALOG_WRITER = "marketplace.catalog_writer"
INTERFACE_REGISTRY = "ui.interface_registry"

# each look type and the payload field of the product selling it (the looks themselves: ``live_looks``)
LOOK_TYPES: dict[str, str] = {
    "avatar_frame": "frame",
    "profile_banner": "banner",
    "profile_background": "background",
    "name_style": "style",
    "level_badge": "style",
    "level_up": "animation",
    "effect": "effect",
    "ambient": "ambient",
    "notification_style": "style",
    "notification_animation": "animation",
    "palette": "palette",
    "badge": "style",
    "title": "style",
    # not sold on its own — an interface wears it
    "navigation": "nav",
}
# a profile background is an ambience: the looks of one are the other's
ALIASES = {"profile_background": "ambient"}
SOCLE = "portalab-socle"
IMAGE_PACKS = Path("/app/packs/builtin")


def builtin_root(env: Mapping[str, str] | None = None) -> Path | None:
    """Where Portalab's own packs are: ``PORTALAB_BUILTIN_PACKS_DIR``, the image's folder, or the repository's
    (development)."""
    configured = (env if env is not None else os.environ).get("PORTALAB_BUILTIN_PACKS_DIR")
    if configured:
        return Path(configured)
    if IMAGE_PACKS.is_dir():
        return IMAGE_PACKS
    repository = Path(__file__).resolve().parents[4] / "packs" / "builtin"
    return repository if repository.is_dir() else None


def builtin_interfaces(root: Path | None = None) -> dict[str, str]:
    """The interfaces Portalab's own packs hold: key → its pack (the socle's first) — none is listed in the
    code; read once."""
    if root is None and _INTERFACES:
        return dict(_INTERFACES)
    out: dict[str, str] = {}
    base = root if root is not None else builtin_root()
    if base is not None and base.is_dir():
        files = sorted(base.glob("*/elements/*/element.json"), key=lambda f: (f.parts[-4] != SOCLE, str(f)))
        for file in files:
            try:
                element = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if element.get("type") == "theme" and isinstance(element.get("look"), str):
                out.setdefault(element["look"], file.parts[-4])
    if root is None:
        _INTERFACES.update(out)
    return out


_INTERFACES: dict[str, str] = {}


def interface_document(key: str, root: Path | None = None) -> dict[str, Any]:
    """An interface Portalab ships: its definition, from its pack's element (``theme.json``) — read by the
    migrations seeding the interfaces and by the demo catalog."""
    base = root if root is not None else builtin_root()
    pack = builtin_interfaces(base).get(key) if base is not None else None
    if base is None or pack is None:
        raise KeyError(key)
    for file in sorted((base / pack / "elements").glob("*/element.json")):
        element = json.loads(file.read_text(encoding="utf-8"))
        if element.get("type") == "theme" and element.get("look") == key:
            document: dict[str, Any] = json.loads((file.parent / "theme.json").read_text(encoding="utf-8"))
            return document
    raise KeyError(key)


def shipped_looks(root: Path | None, pack: str = "*") -> dict[str, list[str]]:
    """The looks Portalab's own packs hold (or one of them: ``pack``), per type — read from their elements
    (the socle's first)."""
    out: dict[str, list[str]] = {}
    if root is None or not root.is_dir():
        return out
    files = sorted(root.glob(f"{pack}/elements/*/element.json"), key=lambda f: (f.parts[-4] != SOCLE, str(f)))
    for file in files:
        try:
            element = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        kind, look = element.get("type"), element.get("look")
        if kind in LOOK_TYPES and isinstance(look, str) and look:
            out.setdefault(ALIASES.get(kind, kind), []).append(look)
    return out


@dataclass(frozen=True, slots=True)
class WidgetContract:
    """A set of data the portal offers packs' widgets: what it holds (its fields, nothing else ever reaches
    the widget), the permission the member viewing it needs, how often it is read again."""

    key: str
    permission: str
    refresh_s: int
    fields: tuple[str, ...]
    descriptions: Mapping[str, str] = field(default_factory=dict)  # plain words, fr/en

    def out(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "permission": self.permission,
            "refresh_s": self.refresh_s,
            "fields": list(self.fields),
            "descriptions": dict(self.descriptions),
        }


# v1 (R26): each reuses data the dashboard already shows, read with the member's own session
WIDGET_CONTRACTS: dict[str, WidgetContract] = {
    contract.key: contract
    for contract in (
        WidgetContract(
            "me.progression",
            "users.self.manage",
            60,
            ("level", "xp", "level_floor", "next_level_at", "coins", "contribution"),
            {
                "en": "Your own progression: your level, your experience towards the next one, your "
                "coins and your contribution.",
                "fr": "Votre propre progression : votre niveau, votre expérience vers le suivant, vos "
                "pièces et votre contribution.",
            },
        ),
        WidgetContract(
            "me.watching",
            "users.self.manage",
            120,
            ("items[].title", "items[].kind", "items[].percent"),
            {
                "en": "What you are watching or reading: each title, its kind and how far you are.",
                "fr": "Ce que vous regardez ou lisez : chaque titre, son genre et où vous en êtes.",
            },
        ),
        WidgetContract(
            "media.recently_added",
            "media.read",
            600,
            ("items[].title", "items[].kind", "items[].year"),
            {
                "en": "What was recently added to the library: titles, kinds and years.",
                "fr": "Ce qui est arrivé récemment dans la bibliothèque : titres, genres et années.",
            },
        ),
        WidgetContract(
            "me.statistics",
            "users.self.manage",
            300,
            ("streak_days", "streak_multiplier", "achievements"),
            {
                "en": "Your own figures: your streak of days, its bonus and how many achievements you "
                "unlocked.",
                "fr": "Vos propres chiffres : votre série de jours, son bonus et le nombre de succès "
                "débloqués.",
            },
        ),
    )
}

# any dashboard widget's own data is a contract too (``widget:<key>``): what that widget shows the member,
# read with the member's session through the dashboard (its permission, and its purchase when it is sold)
WIDGET_DATA = "widget:"
_WIDGET_DATA_KEY = re.compile(r"^[a-z0-9][a-z0-9_.:-]{1,95}$")


def contract_known(key: str) -> bool:
    """A contract the portal offers: one of the catalog's, or a widget's data (never a pack's own widget,
    which holds no data of its own)."""
    if key in WIDGET_CONTRACTS:
        return True
    widget = key.removeprefix(WIDGET_DATA)
    return (
        key.startswith(WIDGET_DATA)
        and bool(_WIDGET_DATA_KEY.fullmatch(widget))
        and "." in widget
        and not widget.startswith("pack.")
    )


# while a pack is analysed or published: the (type, look) pairs it brings itself
PACK_LOOKS: ContextVar[frozenset[tuple[str, str]]] = ContextVar("pack_looks", default=frozenset())


class LiveLooks:
    """The looks Portalab's own packs hold, and those the live packs add, per element type (replaced as a
    whole on every change)."""

    def __init__(self) -> None:
        self._shipped: dict[str, tuple[str, ...]] | None = None  # read on first use
        self._socle: dict[str, frozenset[str]] | None = None
        self._by_type: dict[str, tuple[str, ...]] = {}
        self._held: dict[str, frozenset[str]] = {}
        self.epoch = -1

    def ship(
        self, by_type: Mapping[str, Iterable[str]], socle: Mapping[str, Iterable[str]] | None = None
    ) -> None:
        """The looks of Portalab's own packs (the release's, on or off), per type; ``socle``: those of the
        always-on socle (everyone's, never sold to anyone)."""
        self._shipped = {kind: tuple(dict.fromkeys(keys)) for kind, keys in by_type.items()}
        self._socle = {kind: frozenset(keys) for kind, keys in (socle or {}).items()}

    def free(self, element_type: str) -> frozenset[str]:
        """The socle's looks of this type: free for everyone, whatever a product sells."""
        if self._socle is None:
            root = builtin_root()
            self.ship(shipped_looks(root), shipped_looks(root, SOCLE))
        assert self._socle is not None
        return self._socle.get(ALIASES.get(element_type, element_type), frozenset())

    def shipped(self, element_type: str) -> tuple[str, ...]:
        if self._shipped is None:
            root = builtin_root()
            self.ship(shipped_looks(root), shipped_looks(root, SOCLE))
        assert self._shipped is not None
        return self._shipped.get(ALIASES.get(element_type, element_type), ())

    def replace(
        self,
        by_type: Mapping[str, Iterable[str]],
        epoch: int = -1,
        held: Mapping[str, Iterable[str]] | None = None,
    ) -> None:
        self._by_type = {kind: tuple(dict.fromkeys(keys)) for kind, keys in by_type.items()}
        self._held = {kind: frozenset(keys) for kind, keys in (held or {}).items()}
        self.epoch = epoch

    def held(self, element_type: str) -> frozenset[str]:
        """028 (T081): the looks of this type whose pack is switched off — their owners keep them, shown as
        « currently unavailable », and wear them again when the pack comes back."""
        return self._held.get(element_type, frozenset())

    def listed(self, element_type: str) -> tuple[str, ...]:
        """What owners' lists show: the looks one may wear, then those whose pack is off."""
        known = self.known(element_type)
        return (*known, *sorted(k for k in self.held(element_type) if k not in known))

    def of(self, element_type: str) -> tuple[str, ...]:
        return self._by_type.get(element_type, ())

    def known(self, element_type: str) -> tuple[str, ...]:
        """Portalab's own looks of this type, then the live packs' ones."""
        own = self.shipped(element_type)
        return (*own, *(k for k in self.of(element_type) if k not in own))


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

    async def withdraw(self, actor: Principal, key: str) -> bool:
        """Off sale (its owners keep it); whether it was on sale until now."""
        ...

    async def existing(self, keys: Iterable[str]) -> frozenset[str]:
        """Which of these products the catalog has."""
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
