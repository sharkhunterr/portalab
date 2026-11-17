"""Households (spec 032): a member account (the master) and its profiles, each a member of its own.

* ``household.profiles`` — provided by the household module: who a profile's master is (the economy mirrors
  a profile's amounts on it), what a profile may not do (kept-out features, titles), whether the master let
  it open one title anyway, which profiles stay out of the community;
* ``identity.profile_accounts`` — provided by identity: the accounts behind the profiles (created without a
  login, renamed, deleted), the session acting as one, and the PINs (hashed and throttled like passwords).

Nothing here changes a connected service."""

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Literal, Protocol, get_args, runtime_checkable
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


def genre_key(value: str) -> str:
    """A genre as a profile keeps it out (issue 432: any genre of the catalog): one of the four known ones'
    keys (``horror``…, whatever the language), else its words, lowercased (« Science Fiction » →
    ``science fiction``)."""
    known = genre_of(value)
    return known if known is not None else " ".join(_WORD.findall(value.casefold()))[:60]


def keyword_key(value: str) -> str:
    """Issue 478: a keyword a profile is kept from, as the metadata provider's keywords are matched — its
    words, lowercased, accents folded (« Drogue » → ``drogue``, « Serial-Killer » → ``serial killer``)."""
    folded = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(_WORD.findall("".join(c for c in folded if not unicodedata.combining(c))))[:60]


def keyword_hit(keywords: Any, banned: frozenset[str]) -> bool:
    """Issue 478: whether one of a title's keywords (TMDB's: « serial killer », « drug abuse »…) says one of
    the banned ones — the keyword itself or its whole words (« drug » finds « drug abuse », not
    « drugstore »)."""
    if not banned or not isinstance(keywords, (list, tuple)):
        return False
    for keyword in keywords:
        words = f" {keyword_key(str(keyword))} "
        if any(f" {ban} " in words for ban in banned):
            return True
    return False


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


@dataclass(frozen=True, slots=True)
class Slot:
    """A span of a weekday a profile may watch (``day`` 0 Monday; « HH:MM », ``end`` up to « 24:00 »), with
    its own screen time (``minutes``; ``None``: as long as the span lasts, within the day's)."""

    day: int
    start: str
    end: str
    minutes: int | None = None

    def holds(self, moment: time) -> bool:
        return time.fromisoformat(self.start) <= moment and (
            self.end == "24:00" or moment < time.fromisoformat(self.end)
        )


Mode = Literal["show", "hide", "lock"]  # issue 432: « show » — listed as any title, a padlock, never opened


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
    # issue 432: a weekly plan (Monday first; ``None`` a day without limit), the hours it may watch
    # (« HH:MM », local time) and what its master gave for one day
    week_minutes: tuple[int | None, ...] | None = None
    hours: tuple[str, str] | None = None
    bonus_minutes: int = 0
    bonus_day: date | None = None
    slots: tuple[Slot, ...] = ()  # issue 432: the spans it may watch, each its own screen time
    # issue 439: what its screen time counts — its media (« media »: watched, read, listened to, played) or
    # every minute it spends on the portal (« portal »)
    screen_scope: str = "media"
    # issue 478: other countries whose age ratings count too for this profile (the strictest wins) — its
    # master's choice; ``None``: as the portal's administrator set it
    rating_countries: tuple[str, ...] | None = None
    # issue 478: the warnings its master keeps it from (the CNC's « avertissement », violence, fear…) and
    # how its age is read — the strictest of its countries' ratings, the strictest or the average of every
    # country's
    avoid_warnings: frozenset[str] = frozenset()
    rating_blend: str = "strictest"
    keywords: frozenset[str] = frozenset()  # issue 478: the metadata keywords keeping a title from it

    def slots_on(self, weekday: int) -> tuple[Slot, ...]:
        return tuple(sorted((s for s in self.slots if s.day == weekday), key=lambda s: s.start))

    def window(self, moment: datetime) -> tuple[bool, Slot | None]:
        """Whether it may watch at this (local) moment, and the span it falls in: a day with spans opens
        within them only; a day without, all day (or within the old allowed hours)."""
        spans = self.slots_on(moment.weekday())
        if not spans:
            return self.allowed_at(moment.time()), None
        found = next((span for span in spans if span.holds(moment.time())), None)
        return found is not None, found

    def slot_minutes(self, slot: Slot, day: date) -> int | None:
        """A span's screen time that day, with what its master added for the day."""
        if slot.minutes is None:
            return None
        return slot.minutes + (self.bonus_minutes if self.bonus_day == day else 0)

    def minutes_on(self, day: date) -> int | None:
        """Its screen time on that day: the plan's (or every day's), and what its master added for it."""
        planned = (
            self.week_minutes[day.weekday()]
            if self.week_minutes is not None and len(self.week_minutes) == 7
            else self.daily_minutes
        )
        if planned is None:
            return None
        return planned + (self.bonus_minutes if self.bonus_day == day else 0)

    def allowed_at(self, moment: time) -> bool:
        """Whether this time of day is within its hours (an overnight span too: « 20:00 » to « 07:00 »)."""
        if self.hours is None:
            return True
        start, end = (time.fromisoformat(h) for h in self.hours)
        return start <= moment < end if start <= end else moment >= start or moment < end

    @property
    def limits_titles(self) -> bool:
        return (
            self.max_age is not None
            or not self.allow_unrated
            or bool(self.genres or self.types or self.titles or self.avoid_warnings or self.keywords)
        )

    @property
    def restricts(self) -> bool:
        """Whether anything at all is restricted (titles, features, screen time, the services)."""
        timed = (
            self.daily_minutes is not None
            or self.week_minutes is not None
            or self.hours is not None
            or bool(self.slots)
        )
        return self.limits_titles or bool(self.blocked) or timed or not self.services

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
    # issue 421: the games' systems without an age in their letters (IGDB's, as RomM keeps them)
    "ESRB EC": 3,
    "ESRB E": 0,
    "ESRB T": 13,
    "ESRB M": 17,
    "ESRB AO": 18,
    "CERO A": 0,
    "CERO B": 12,
    "CERO C": 15,
    "CERO D": 17,
    "CERO Z": 18,
    "ACB G": 0,
    "ACB PG": 8,
    "ACB M": 15,
    "CLASS IND L": 0,
    "GRAC ALL": 0,
}
# issue 421: ratings given in words (IGDB's PEGI « Twelve », GRAC « Fifteen »…)
RATING_WORDS = {
    "THREE": "3",
    "SEVEN": "7",
    "TEN": "10",
    "TWELVE": "12",
    "FOURTEEN": "14",
    "FIFTEEN": "15",
    "SIXTEEN": "16",
    "EIGHTEEN": "18",
}
UNRATED_WORDS = frozenset({"RP", "RC", "TESTING", "NR", "UNRATED"})
_NUMBER = re.compile(r"\d{1,2}")


def age_of(rating: str | None) -> int | None:
    """The minimum age a rating stands for, ``None`` when unrated or unknown (« NR », « Unrated »); a media
    server's country prefix is dropped (Plex: « fr/12 », « de/16 »)."""
    text = " ".join((rating or "").upper().replace("_", " ").split())
    if "/" in text:
        text = text.split("/", 1)[1].strip()
    if not text or text.split()[-1] in UNRATED_WORDS:
        return None
    text = " ".join(RATING_WORDS.get(word, word) for word in text.split())
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
        """The profiles kept out of the community — issue 443: every profile of a common pot (its master
        stands for the household)."""
        ...

    async def profiles(self) -> frozenset[UUID]:
        """Every household profile (they never sign in: never dormant, never matched with a service)."""
        ...

    async def profiles_of(self, owner: UUID) -> frozenset[UUID]:
        """A master's profiles (they follow its account's deletion)."""
        ...

    async def economy_of(self, user: UUID) -> str:
        """Issue 443: how a master's household earns — ``pot`` (its profiles' gains, items too, also the
        master's: the household's pot; the profiles kept out of the community) or ``dispatch`` (each profile
        its own wallet, in the community as itself or anonymous). A profile's is its master's."""
        ...

    async def anonymous(self) -> frozenset[UUID]:
        """Issue 443: the dispatched profiles their master shows anonymously in the community."""
        ...

    async def exists(self, user: UUID) -> bool:
        """Issue 445: whether ``user`` is in a household — a profile, or a master who made one (« My
        household » is shown to them only)."""
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


class ProfileNoProjects(Forbidden):
    """Issue 443: a household profile never takes part in the community's projects (fund, vote, join,
    propose, launch) — its master does, for the household."""

    def __init__(self) -> None:
        super().__init__(
            "Household profiles do not take part in community projects.", code="household.no_projects"
        )


async def refuse_profile(capabilities: Any, actor: Principal | None, user: UUID | None) -> None:
    """Issue 443: refuses a household profile (acting as one, or a profile's account) a community project."""
    if actor is not None and actor.profile_of is not None:
        raise ProfileNoProjects()
    if user is None:
        return
    try:
        providers = capabilities.system_providers(CAPABILITY)
        owner = await providers[0].provider.owner_of(user) if providers else None
    except Exception:
        owner = None
    if owner is not None:
        raise ProfileNoProjects()


async def pot_master(capabilities: Any, user: UUID) -> UUID | None:
    """Issue 443: the master of a profile whose household shares a common pot — what the profile gets (items
    too) is duplicated on it; ``None`` for anyone else (a master, a dispatched profile, no household)."""
    try:
        providers = capabilities.system_providers(CAPABILITY)
        if not providers:
            return None
        household = providers[0].provider
        owner = await household.owner_of(user)
        if owner is None:
            return None
        economy = getattr(household, "economy_of", None)
        if economy is not None and await economy(user) != "pot":
            return None
        return owner  # type: ignore[no-any-return]
    except Exception:
        return None


def copy_key(profile: UUID, key: str) -> str:
    """Issue 443: the idempotency key of a master's copy of a profile's item — once, and found again by its
    prefix (``household:<profile>:``) when the pot is given back."""
    return f"household:{profile}:{hashlib.sha256(key.encode('utf-8')).hexdigest()[:40]}"
