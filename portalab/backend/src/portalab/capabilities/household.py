"""Households (spec 032): a member account (the master) and its profiles, each a member of its own.

* ``household.profiles`` — provided by the household module: who a profile's master is (the economy mirrors
  a profile's amounts on it), what a profile may not do (kept-out features, titles), whether the master let
  it open one title anyway, which profiles stay out of the community;
* ``identity.profile_accounts`` — provided by identity: the accounts behind the profiles (created without a
  login, renamed, deleted), the session acting as one, and the PINs (hashed and throttled like passwords).

Nothing here changes a connected service."""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, get_args, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal
from portalab.core.errors import BadRequest, Forbidden

CAPABILITY = "household.profiles"
PROFILE_ACCOUNTS = "identity.profile_accounts"

Kind = Literal["owner", "standard", "child", "custom"]
KINDS: tuple[str, ...] = get_args(Kind)
Feature = Literal["shop", "requests", "ai", "community", "games", "support"]
FEATURES: tuple[str, ...] = get_args(Feature)
AGES: tuple[int, ...] = (0, 6, 10, 12, 14, 16, 18)
# 032: genres a master may keep from a profile whatever their rating, by the words their tags use (en, fr)
GENRE_WORDS: dict[str, tuple[str, ...]] = {
    "horror": ("horror", "horreur", "épouvante", "epouvante"),
    "thriller": ("thriller",),
    "crime": ("crime", "policier"),
    "war": ("war", "guerre"),
}
GENRES: tuple[str, ...] = tuple(GENRE_WORDS)
# 032: the kinds of content a master may keep from a profile, by the catalog kinds they gather
TYPE_KINDS: dict[str, tuple[str, ...]] = {
    "movies": ("movie",),
    "series": ("series", "season", "episode"),
    "books": ("book", "comic", "manga", "magazine"),
    "audiobooks": ("audiobook",),
    "music": ("artist", "album", "track"),
    "games": ("game",),
}
TYPES: tuple[str, ...] = tuple(TYPE_KINDS)
SCREEN_MINUTES: tuple[int, ...] = (15, 30, 45, 60, 90, 120, 180, 240, 300)
_WORD = re.compile(r"[^\W\d_]+")


def genre_of(tag: str) -> str | None:
    """The kept-out genre a title's genre tag stands for (« Épouvante-horreur » → ``horror``), if any."""
    words = set(_WORD.findall(tag.casefold()))
    return next((genre for genre, names in GENRE_WORDS.items() if words & set(names)), None)


# the permissions a kept-out feature withholds from a profile, whatever its roles grant
FEATURE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "shop": ("marketplace.purchase",),
    "requests": ("media.request",),
    "ai": ("ai.use",),
    "community": ("community.participate", "community.propose"),
    "games": ("games.play",),
    "support": ("tickets.create", "tickets.comment", "feedback.submit"),
}


Mode = Literal["hide", "lock"]


@dataclass(frozen=True, slots=True)
class Restrictions:
    """What a profile may not reach: titles rated above ``max_age`` (``None``: no limit — its age today when
    its master gave a birth date), unrated titles unless ``allow_unrated``, and the kept-out ``blocked``
    features. Titles kept from it are hidden (``hide``) or shown locked (``lock``); ``requests``: whether it
    may ask its master for one."""

    max_age: int | None = None
    allow_unrated: bool = True
    blocked: frozenset[str] = frozenset()
    mode: Mode = "hide"
    requests: bool = True
    genres: frozenset[str] = frozenset()  # kept out whatever their rating (``horror``…)
    types: frozenset[str] = frozenset()  # kinds of content kept out (``books``, ``games``…)
    titles: frozenset[str] = frozenset()  # titles its master kept out one by one
    daily_minutes: int | None = None  # screen time a day in the portal's player and reader
    services: bool = True  # may open a title in its service (Plex, Grimmory, RomM…), not only in the portal

    @property
    def limits_titles(self) -> bool:
        return (
            self.max_age is not None
            or not self.allow_unrated
            or bool(self.genres or self.types or self.titles)
        )

    @property
    def restricts(self) -> bool:
        """Whether anything at all is restricted (titles, features, screen time, the services)."""
        return self.limits_titles or bool(self.blocked) or self.daily_minutes is not None or not self.services

    @property
    def kinds(self) -> frozenset[str]:
        """The catalog kinds its kept-out types gather."""
        return frozenset(kind for kept in self.types for kind in TYPE_KINDS.get(kept, ()))

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
    """The minimum age a rating stands for, ``None`` when unrated or unknown (« NR », « Unrated »); a media
    server's country prefix is dropped (Plex: « fr/12 », « de/16 »)."""
    text = " ".join((rating or "").upper().replace("_", " ").split())
    if "/" in text:
        text = text.split("/", 1)[1].strip()
    if not text:
        return None
    if text in RATING_AGES:
        return RATING_AGES[text]
    found = _NUMBER.search(text)
    return min(int(found.group()), 21) if found else None


def strictest_age(ratings: Iterable[str | None]) -> int | None:
    """032: the strictest age among a title's ratings (TMDB's countries, the media server's): a child's limit
    holds to it — France rates many horror films 12, the United States R. ``None``: no known rating."""
    ages = [age for rating in ratings if (age := age_of(rating)) is not None]
    return max(ages) if ages else None


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

    async def profiles(self) -> frozenset[UUID]:
        """Every household profile (they never sign in: never dormant, never matched with a service)."""
        ...

    async def profiles_of(self, owner: UUID) -> frozenset[UUID]:
        """A master's profiles (they follow its account's deletion)."""
        ...


@dataclass(frozen=True, slots=True)
class AccountCard:
    """What a household shows of a member's account."""

    id: UUID
    display_name: str
    has_avatar: bool
    live: bool  # an active account
    last_seen_at: datetime | None = None


class WrongPin(Forbidden):
    default_code = "household.wrong_pin"
    default_title = "Wrong PIN"


class PinThrottled(BadRequest):
    status = 429
    default_code = "household.pin_throttled"
    default_title = "Too many wrong PINs"


@runtime_checkable
class ProfileAccounts(Protocol):
    async def create(self, display_name: str, actor: Principal) -> UUID:
        """A profile's account: no login, a name that needs not be unique, its welcome to come."""
        ...

    async def rename(self, user: UUID, display_name: str) -> None: ...

    async def remove(self, user: UUID, actor: Principal) -> None:
        """Its deletion, at once (nobody signs in to cancel it); every browser acting as it signed out."""
        ...

    async def cards(self, users: Sequence[UUID]) -> Mapping[UUID, AccountCard]: ...

    async def act(self, session_id: UUID, owner: UUID, target: UUID | None) -> None:
        """The session of ``owner`` acts as ``target`` from now (``None``: the account itself)."""
        ...

    async def chosen(self, session_id: UUID) -> bool:
        """Whether « Who's there? » was answered since this session signed in."""
        ...

    async def hash_pin(self, pin: str) -> str: ...

    async def verify_pin(self, subject: UUID, pin_hash: str, pin: str) -> None:
        """Raise ``WrongPin`` (counted, slowing the next tries) or ``PinThrottled``."""
        ...


PROFILE_ACCOUNTS_SPEC = CapabilitySpec(
    name=PROFILE_ACCOUNTS,
    version="1.0",
    protocol=ProfileAccounts,
    multi_provider=False,
    description="The accounts and sessions behind household profiles, and their PINs (owned by identity).",
)


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=Household,
    multi_provider=False,
    description="Households: profiles' masters, restrictions and access grants (owned by household).",
)
