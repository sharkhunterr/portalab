"""Community contracts (spec 012, contracts/community-contracts.md). Community is a **composition layer**:
it owns surfaces (directory, profiles, feed, discovery, community events; proposals and votes in slice D)
and no engines. Modules and plugins extend it:

* ``register_profile_section`` — a profile block computed per (owner, viewer), governed by a 021 datum
  class (a section the viewer may not see is simply absent); each section fails independently;
* ``register_discovery_shelf`` — a discovery list for a viewer (visibility is the provider's job).
There is deliberately no friends/followers graph, direct messages, likes, reactions or chat."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from portalab.core.authz_port import Principal

SectionState = Literal["available", "no-data", "unavailable", "stale"]


@dataclass(frozen=True, slots=True)
class SectionResult:
    state: SectionState
    data: Mapping[str, Any] = field(default_factory=dict)


SectionProvider = Callable[[UUID, Principal], Awaitable[SectionResult]]


@dataclass(frozen=True, slots=True)
class ProfileSection:
    key: str
    owner: str
    datum_class: str  # 021 visibility of the profile owner decides whether the viewer sees it
    provider: SectionProvider = field(compare=False)
    order: int = 100
    permission: str = "community.read"
    label_key: str = ""


ShelfProvider = Callable[[Principal, int], Awaitable[Sequence[Mapping[str, Any]]]]


@dataclass(frozen=True, slots=True)
class DiscoveryShelf:
    key: str
    owner: str
    provider: ShelfProvider = field(compare=False)
    order: int = 100
    label_key: str = ""
    empty_action: str | None = None  # a route offered when the shelf is empty


class _Owned[T]:
    def __init__(self) -> None:
        self._items: dict[str, T] = {}

    def _register(self, key: str, owner: str, item: T) -> T:
        existing = self._items.get(key)
        if existing is not None and getattr(existing, "owner", owner) != owner:
            raise ValueError(f"{key!r} is already registered by {getattr(existing, 'owner', '?')}")
        self._items[key] = item
        return item

    def get(self, key: str) -> T | None:
        return self._items.get(key)

    def unregister(self, owner: str) -> int:
        doomed = [k for k, v in self._items.items() if getattr(v, "owner", None) == owner]
        for key in doomed:
            del self._items[key]
        return len(doomed)


class SectionRegistry(_Owned[ProfileSection]):
    def register(self, section: ProfileSection) -> ProfileSection:
        return self._register(section.key, section.owner, section)

    def all(self) -> list[ProfileSection]:
        return sorted(self._items.values(), key=lambda s: (s.order, s.key))


class ShelfRegistry(_Owned[DiscoveryShelf]):
    def register(self, shelf: DiscoveryShelf) -> DiscoveryShelf:
        return self._register(shelf.key, shelf.owner, shelf)

    def all(self) -> list[DiscoveryShelf]:
        return sorted(self._items.values(), key=lambda s: (s.order, s.key))


default_sections = SectionRegistry()
default_shelves = ShelfRegistry()


def register_profile_section(
    section: ProfileSection, registry: SectionRegistry = default_sections
) -> ProfileSection:
    return registry.register(section)


def register_discovery_shelf(
    shelf: DiscoveryShelf, registry: ShelfRegistry = default_shelves
) -> DiscoveryShelf:
    return registry.register(shelf)
