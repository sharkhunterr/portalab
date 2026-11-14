"""``identity.household`` (spec 032): households — a member account (the master) and its profiles, each a
member of its own. Other modules ask here who a profile's master is (the economy mirrors a profile's amounts
on it), what a profile may not do (kept-out features, a maximum age rating) and whether the master let it
open one title anyway. Identity owns the households; nothing here changes a connected service."""

import re
from dataclasses import dataclass
from typing import Literal, Protocol, get_args, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec

CAPABILITY = "identity.household"

Kind = Literal["owner", "standard", "child", "custom"]
KINDS: tuple[str, ...] = get_args(Kind)
Feature = Literal["shop", "requests", "ai", "community", "games", "support"]
FEATURES: tuple[str, ...] = get_args(Feature)
AGES: tuple[int, ...] = (0, 6, 10, 12, 14, 16, 18)

# the permissions a kept-out feature withholds from a profile, whatever its roles grant
FEATURE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "shop": ("marketplace.purchase",),
    "requests": ("media.request",),
    "ai": ("ai.use",),
    "community": ("community.participate", "community.propose"),
    "games": ("games.play",),
    "support": ("tickets.create", "tickets.comment", "feedback.submit"),
}


@dataclass(frozen=True, slots=True)
class Restrictions:
    """What a profile may not reach: titles rated above ``max_age`` (``None``: no limit), unrated titles
    unless ``allow_unrated``, and the kept-out ``blocked`` features."""

    max_age: int | None = None
    allow_unrated: bool = True
    blocked: frozenset[str] = frozenset()

    @property
    def limits_titles(self) -> bool:
        return self.max_age is not None or not self.allow_unrated

    def withholds(self, permission: str) -> bool:
        return any(permission in FEATURE_PERMISSIONS.get(feature, ()) for feature in self.blocked)

    def allows_age(self, age: int | None) -> bool:
        """Whether a title of this minimum ``age`` (``None``: unrated) may be shown."""
        if age is None:
            return self.allow_unrated
        return self.max_age is None or age <= self.max_age


# the ratings of the main systems that are no age (US film/TV, UK, FR): the others carry their age (« 12 »,
# « -16 », « FSK 12 », « 12A », « PG-13 »…); an unknown rating counts as unrated
RATING_AGES: dict[str, int] = {
    "G": 0,
    "U": 0,
    "TP": 0,
    "TOUS PUBLICS": 0,
    "TOUT PUBLIC": 0,
    "ALL": 0,
    "AL": 0,
    "TV-Y": 0,
    "TV-G": 0,
    "TV-Y7": 7,
    "TV-Y7-FV": 7,
    "PG": 8,
    "TV-PG": 10,
    "PG-13": 13,
    "TV-14": 14,
    "R": 17,
    "TV-MA": 17,
    "NC-17": 18,
    "X": 18,
}
_NUMBER = re.compile(r"\d{1,2}")


def age_of(rating: str | None) -> int | None:
    """The minimum age a rating stands for, ``None`` when unrated or unknown (« NR », « Unrated »)."""
    text = " ".join((rating or "").upper().replace("_", " ").split())
    if not text:
        return None
    if text in RATING_AGES:
        return RATING_AGES[text]
    found = _NUMBER.search(text)
    return min(int(found.group()), 21) if found else None


@runtime_checkable
class Household(Protocol):
    async def owner_of(self, user: UUID) -> UUID | None:
        """The master of a profile; ``None`` for a master, a member without household or an unknown user."""
        ...

    async def restrictions_of(self, user: UUID) -> Restrictions | None:
        """A profile's restrictions; ``None`` when nothing is restricted (masters, members, open profiles)."""
        ...

    async def granted(self, user: UUID, kind: str, ref: str) -> bool:
        """Whether the master let this profile open this one object (an approved access request in force)."""
        ...

    async def grants(self, user: UUID, kind: str) -> frozenset[str]:
        """Every object of this kind the master let this profile open (approved requests in force)."""
        ...

    async def hidden(self) -> frozenset[UUID]:
        """The profiles their master keeps out of the community."""
        ...


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=Household,
    multi_provider=False,
    description="Households: profiles' masters, restrictions and access grants (owned by identity).",
)
