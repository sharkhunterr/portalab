"""032: what a household profile's age rating keeps from it. A profile its master restricted to an age (and,
maybe, to rated titles only) is never served a film or a series rated above it — nor the series' seasons and
episodes — from the catalog, the detail pages, the shelves, the search, the recommendations, the feed, the
dashboard widgets or the players, unless its master let it open that title (an approved access request).

Ratings are the metadata provider's (TMDB's ``certification``, stored with each film's and series' metadata) —
issue 438: the portal's country's one counts, the strictest of the others only when it has none;
other kinds (books, music, games, live TV) have no rating and are never held back. Members without a
restriction cost one cached lookup: nothing is computed for them."""

import asyncio
import time
from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Uuid, all_, and_, any_, delete, func, literal, literal_column, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import aliased

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.household import CAPABILITY as HOUSEHOLD
from portalab.capabilities.household import (
    Household,
    Restrictions,
    age_of,
    genre_key,
    keyword_hit,
    strictest_age,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Forbidden
from portalab.modules.media.models import (
    Activity,
    MediaObject,
    ObjectMetadata,
    ObjectTag,
    PlaybackSession,
    ScreenBeat,
)
from portalab.modules.media.region import country_of, system_language

# issue 432: every kind a rating may hold to — the unrated rule too (books, games: « unrated titles » off
# keeps their unrated ones out as well); music has no rating system
RATED = ("movie", "series", "book", "comic", "manga", "magazine", "audiobook", "game")
CACHE_S = 30.0
AGES_CACHE_S = 300.0  # issue 437: every title's age, for the catalog's filter
COUNTRY_CACHE_S = 60.0  # issue 438: the system language's country
BEATS_KEPT = timedelta(days=8)  # issue 439: a profile's minutes on the portal, kept a week
MINUTE = timedelta(minutes=1)
AGE_FILTERS = ("mine", "0", "6", "10", "12", "14", "16", "18")
ASKABLE = (
    "age",
    "unrated",
    "genre",
    "keyword",
    "warning",
)  # what an access request may open (not the master's own choices)
IDS = ("id", "object_id", "media_id", "work_id")


class ScreenTimeUp(Forbidden):
    default_code = "household.screen_time_up"
    default_title = "Screen time spent for today"


class Restricted(Forbidden):
    default_code = "household.restricted"
    default_title = "This title is not open to this profile"


def labelled(data: Mapping[str, Any] | None, server: str | None) -> list[tuple[str, str]]:
    """A title's age ratings by source: TMDB's countries (« FR », « US »…), else its single certification
    (details found before 032), and the media server's (« server »)."""
    data = data or {}
    found: list[tuple[str, str]] = []
    countries = data.get("certifications")
    if isinstance(countries, Mapping) and countries:
        found += [(str(c), str(r)) for c, r in countries.items() if r]
    elif data.get("certification"):
        found.append(("TMDB", str(data["certification"])))
    if server:
        found.append(("server", server))
    return found


def own_first(sources: list[tuple[str, str]], country: str | None) -> list[tuple[str, str]]:
    """Issue 438: the country's ratings first (TMDB's, the media server's « fr/12 »), then the others."""
    if not country:
        return sources
    mine = [s for s in sources if _of_country(s, country)]
    return mine + [s for s in sources if not _of_country(s, country)]


def _of_country(source: tuple[str, str], country: str) -> bool:
    label, value = source
    return label.upper() == country or (label == "server" and value.upper().startswith(f"{country}/"))


def local_age(sources: Iterable[tuple[str, str]], country: str | None) -> int | None:
    """Issue 438: the age a title is rated for in the portal's country — its rating there (TMDB's, else the
    media server's « fr/12 »), the strictest of the others only when that country rates it not."""
    sources = list(sources)
    if country:
        country = country.upper()
        ages = [a for s in sources if _of_country(s, country) and (a := age_of(s[1])) is not None]
        if ages:
            return max(ages)
    return strictest_age(v for _, v in sources)


# issue 478: a title's releases by the way one watches them — the TV, the platforms and discs, the cinema
TIERS: dict[str, tuple[str, ...]] = {
    "tv": ("tv",),
    "home": ("digital", "physical"),
    "cinema": ("cinema", "cinema_limited", "premiere"),
}
DEFAULT_ORDER = (
    "tv,home,cinema"  # « home viewing first »; the administrator orders them (media.ratings.order)
)


def order_of(order: str | None) -> list[str]:
    """The tiers in the administrator's order (« strictest »: none — every rating at once)."""
    if order == "strictest":
        return []
    tiers = [tier for tier in str(order or DEFAULT_ORDER).split(",") if tier in TIERS]
    return tiers if sorted(tiers) == sorted(TIERS) else DEFAULT_ORDER.split(",")


def country_age(
    data: Mapping[str, Any] | None, server: str | None, country: str, order: str = DEFAULT_ORDER
) -> int | None:
    """Issue 478: the age a country rates a title for, in the administrator's order of its releases — the
    first kind known counting (the strictest within it; the media server's own rating, when it is that
    country's, with the cinema's), or the strictest of them all; ``None`` when that country's releases are
    not known."""
    local = country.upper()
    mine = [
        r
        for r in (data or {}).get("releases") or []
        if isinstance(r, Mapping) and str(r.get("country", "")).upper() == local
    ]
    own_server = server is not None and _of_country(("server", server), local)

    def ages_in(kinds: Iterable[str], with_server: bool) -> list[int]:
        wanted = set(kinds)
        found = [
            age
            for r in mine
            if r.get("type") in wanted and (age := age_of(str(r.get("certification")))) is not None
        ]
        if with_server and own_server and (age := age_of(str(server))) is not None:
            found.append(age)
        return found

    if not mine:
        return None
    tiers = order_of(order)
    if not tiers:  # the strictest of them all
        every = ages_in([kind for kinds in TIERS.values() for kind in kinds], True)
        return max(every) if every else None
    for tier in tiers:
        if ages := ages_in(TIERS[tier], tier == "cinema"):
            return max(ages)
    return None


# issue 478: the rating boards' descriptors by family (TMDB's, in English; a letter for the Netherlands')
WARNING_WORDS: dict[str, tuple[str, ...]] = {
    "violence": ("violen", "injur", "gor", "brutal"),
    "fear": ("threat", "fear", "frighten", "stressful", "disturbing", "horror"),
    "language": ("language", "profan", "swear"),
    "drugs": ("drug", "alcohol", "tobacco", "smok", "risk behavior"),
    "sex": ("sex", "nudity", "erotic"),
    "self_harm": ("self-harm", "self harm", "suicid"),
    "discrimination": ("discriminat", "racis"),
    "mature": ("mature", "not recommended for"),
}
WARNING_LETTERS = {
    "v": "violence",
    "l": "language",
    "d": "drugs",
    "s": "sex",
    "a": "fear",
    "g": "discrimination",
}


def warnings_of(data: Mapping[str, Any] | None) -> set[str]:
    """Issue 478: the families of the warnings a title's ratings carry (« Violence », « Threat »…)."""
    found: set[str] = set()
    for release in (data or {}).get("releases") or []:
        if not isinstance(release, Mapping):
            continue
        for raw in release.get("descriptors") or []:
            text = str(raw).strip().lower()
            if text in WARNING_LETTERS:
                found.add(WARNING_LETTERS[text])
                continue
            found |= {kind for kind, words in WARNING_WORDS.items() if any(w in text for w in words)}
    return found


def _cnc_warns(data: Mapping[str, Any], cnc: tuple[frozenset[int], frozenset[tuple[str, int]]]) -> bool:
    """Whether the CNC rated this film « tous publics avec avertissement »: its visa named by its French
    release, else its title (French or original, folded) and year (±1)."""
    from portalab.modules.media.ratings.cnc import VISA_NOTE, fold

    visas, keys = cnc
    for release in data.get("releases") or []:
        if isinstance(release, Mapping) and str(release.get("country", "")).upper() == "FR":
            match = VISA_NOTE.search(str(release.get("note") or ""))
            if match and int(match.group(1)) in visas:
                return True
    year = str(data.get("release_date") or "")[:4]
    if not year.isdigit():
        return False
    titles = {fold(str(t)) for t in (data.get("title"), data.get("original_title")) if t}
    return any((key, int(year) + delta) in keys for key in titles if key for delta in (-1, 0, 1))


def _ages_by_country(
    data: Mapping[str, Any] | None, server: str | None, country: str | None, order: str
) -> dict[str, int]:
    """Every country's age for a title (its releases' in the order, else its one certification)."""
    data = data or {}
    codes = {str(r.get("country", "")).upper() for r in data.get("releases") or [] if isinstance(r, Mapping)}
    certifications = data.get("certifications") or {}
    if isinstance(certifications, Mapping):
        codes |= {str(c).upper() for c in certifications}
    if country:
        codes.add(country.upper())
    out: dict[str, int] = {}
    for code in sorted(c for c in codes if c):
        age = country_age(data, server if country and code == country.upper() else None, code, order)
        if age is None and isinstance(certifications, Mapping) and certifications.get(code):
            age = age_of(str(certifications[code]))
        if age is not None:
            out[code] = age
    return out


def title_age(
    data: Mapping[str, Any] | None,
    server: str | None,
    country: str | None,
    order: str = DEFAULT_ORDER,
    also: Iterable[str] = (),
    blend: str = "strictest",
) -> int | None:
    """Issue 478: the age a title is held to — as the portal's country rates it, in the administrator's order
    of its releases (by default as it is watched at home: Mad Max: Fury Road, « tous publics » at the cinema,
    -12 on TV, is 12; ``country_age``); when its releases are not known (details looked up before), as issue
    438 rated it (``local_age``). The other countries the administrator chose (``also``) count too: the
    strictest of them wins (Resident Evil, -12 in France, R in the United States: 17) — a country that does
    not rate the title does not count. A household profile may be read by the average of every country's
    rating instead (``blend="average"``, its master's choice), rounded to the nearest year, or by the
    strictest of every country's (``blend="highest"``)."""
    if blend in ("average", "highest"):
        ages = list(_ages_by_country(data, server, country, order).values())
        if ages:
            return max(ages) if blend == "highest" else int(sum(ages) / len(ages) + 0.5)
    own = country_age(data, server, country, order) if country else None
    base = own if own is not None else local_age(labelled(data, server), country)
    found = [base] if base is not None else []
    certifications = (data or {}).get("certifications") or {}
    for other in also:
        if country and other.upper() == country.upper():
            continue
        age = country_age(data, None, other, order)
        if age is None and isinstance(certifications, Mapping) and certifications.get(other):
            age = age_of(str(certifications[other]))
        if age is not None:
            found.append(age)
    return max(found) if found else None


def excluded(column: Any, blocked: frozenset[UUID]) -> Any:
    """A clause keeping the rows whose ``column`` is none of the ``blocked`` titles (one array parameter,
    however many there are)."""
    return column != all_(literal(list(blocked), ARRAY(Uuid())))


def viewer_of(viewer: Principal | UUID | None) -> UUID | None:
    if isinstance(viewer, Principal):
        return viewer.acting_for or viewer.user_id
    return viewer


class TitleGate:
    def __init__(self, database: Database, capabilities: CapabilityRegistry) -> None:
        self.database = database
        self.capabilities = capabilities
        self._cache: dict[UUID, tuple[float, frozenset[UUID]]] = {}
        self._ages: tuple[float, str | None, dict[UUID, int | None]] | None = None
        self._country: tuple[float, str | None] | None = None
        self.cnc: Any = None  # issue 478: the CNC's visas (``CncVisas``), set by the module
        self._order: tuple[float, str] | None = None
        self._also: tuple[float, tuple[str, ...]] | None = None
        self._warned: tuple[float, tuple[frozenset[int], frozenset[tuple[str, int]]]] | None = None
        self.briefs: Any = None  # issue 478: the metadata provider's word on a title outside the library

    async def country(self) -> str | None:
        """Issue 438: the country whose age ratings count (the system language's), kept a minute."""
        if self._country is not None and time.monotonic() - self._country[0] < COUNTRY_CACHE_S:
            return self._country[1]
        found = country_of(await system_language(self.capabilities))
        self._country = (time.monotonic(), found)
        return found

    async def cnc_warned(self) -> tuple[frozenset[int], frozenset[tuple[str, int]]]:
        """Issue 478: the CNC's films « tous publics avec avertissement » — by visa, and by folded title and
        year (to match a film whose release does not name its visa), kept an hour."""
        if self._warned is not None and time.monotonic() - self._warned[0] < 3600:
            return self._warned[1]
        found: tuple[frozenset[int], frozenset[tuple[str, int]]] = (frozenset(), frozenset())
        if self.cnc is not None:
            found = await self.cnc.warned()
        self._warned = (time.monotonic(), found)
        return found

    @staticmethod
    def _warnings(
        data: Mapping[str, Any] | None, cnc: tuple[frozenset[int], frozenset[tuple[str, int]]] | None
    ) -> set[str]:
        """A title's warnings by family — the rating boards' descriptors, and the CNC's « avertissement »."""
        found = warnings_of(data)
        if cnc is not None and data and _cnc_warns(data, cnc):
            found.add("cnc")
        return found

    async def blend_for(self, viewer: Principal | UUID | None) -> str:
        """Issue 478: how this viewer's ages are read — a profile's master may choose the average."""
        restrictions = await self.restrictions(viewer) if viewer is not None else None
        return restrictions.rating_blend if restrictions is not None else "strictest"

    async def countries_for(self, viewer: Principal | UUID | None) -> tuple[str, ...]:
        """Issue 478: the other countries whose ratings count for this viewer — its master's choice for a
        household profile, else the administrator's."""
        restrictions = await self.restrictions(viewer) if viewer is not None else None
        if restrictions is not None and restrictions.rating_countries is not None:
            return restrictions.rating_countries
        return await self.also_countries()

    async def also_countries(self) -> tuple[str, ...]:
        """Issue 478: the other countries whose ratings count too (``media.ratings.alsoCountries``), kept a
        minute."""
        if self._also is not None and time.monotonic() - self._also[0] < COUNTRY_CACHE_S:
            return self._also[1]
        found: tuple[str, ...] = ()
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                value = (await providers[0].provider.get("media.ratings.alsoCountries")).value or []
                found = tuple(str(c).upper() for c in value if isinstance(c, str))
        except Exception:  # noqa: S110 — the portal's country alone
            pass
        self._also = (time.monotonic(), found)
        return found

    async def rating_order(self) -> str:
        """Issue 478: the administrator's order of a title's ratings (``media.ratings.order``), kept a
        minute."""
        if self._order is not None and time.monotonic() - self._order[0] < COUNTRY_CACHE_S:
            return self._order[1]
        found = DEFAULT_ORDER
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                found = str((await providers[0].provider.get("media.ratings.order")).value or DEFAULT_ORDER)
        except Exception:  # noqa: S110 — the default order holds
            pass
        self._order = (time.monotonic(), found)
        return found

    def _household(self) -> Household | None:
        providers = self.capabilities.system_providers(HOUSEHOLD)
        return providers[0].provider if providers else None

    async def restrictions(self, viewer: Principal | UUID | None) -> Restrictions | None:
        user, household = viewer_of(viewer), self._household()
        if user is None or household is None:
            return None
        restrictions = await household.restrictions_of(user)
        return restrictions if restrictions is not None and restrictions.limits_titles else None

    async def blocked(self, viewer: Principal | UUID | None) -> frozenset[UUID]:
        """The titles (and their seasons and episodes) kept from this viewer — empty for nearly everyone."""
        restrictions = await self.restrictions(viewer)
        user, household = viewer_of(viewer), self._household()
        if restrictions is None or user is None or household is None:
            return frozenset()
        cached = self._cache.get(user)
        if cached is not None and time.monotonic() - cached[0] < CACHE_S:
            return cached[1]
        granted = await household.grants(user, "media")
        country = await self.country()
        order = await self.rating_order()
        also = (
            restrictions.rating_countries
            if restrictions.rating_countries is not None
            else await self.also_countries()
        )
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(
                        MediaObject.id,
                        MediaObject.kind,
                        ObjectMetadata.data,
                        MediaObject.effective["content_rating"].astext,
                    )
                    .outerjoin(
                        ObjectMetadata,
                        (ObjectMetadata.object_id == MediaObject.id) & (ObjectMetadata.status == "found"),
                    )
                    .where(MediaObject.kind.in_(RATED))
                )
            ).all()
            blend = restrictions.rating_blend
            avoid = restrictions.avoid_warnings
            cnc = await self.cnc_warned() if "cnc" in avoid else None
            works = {
                work
                for work, kind, data, server in rows
                if str(work) not in granted
                and (
                    not restrictions.allows_age(title_age(data, server, country, order, also, blend))
                    # issue 478: a warning its master keeps it from, whatever its age
                    or bool(avoid and avoid & self._warnings(data, cnc))
                    # issue 478: or one of the metadata's keywords it is kept from
                    or keyword_hit((data or {}).get("keywords"), restrictions.keywords)
                )
            }
            if restrictions.genres:  # kept out whatever their rating (horror…)
                tags = await session.execute(
                    select(ObjectTag.object_id, ObjectTag.value)
                    .join(MediaObject, MediaObject.id == ObjectTag.object_id)
                    .where(ObjectTag.tag_kind == "genre", MediaObject.kind.in_(RATED))
                )
                works |= {
                    work
                    for work, tag in tags
                    if str(work) not in granted and genre_key(str(tag)) in restrictions.genres
                }
            works |= {
                UUID(title) for title in restrictions.titles
            }  # kept out one by one: no request opens it
            kept_kinds: set[UUID] = set()
            if restrictions.kinds:  # kinds of content kept out (books, games…)
                kept_kinds = set(
                    await session.scalars(
                        select(MediaObject.id).where(MediaObject.kind.in_(restrictions.kinds))
                    )
                )
            season = aliased(MediaObject)
            children: set[UUID] = set()
            if works:
                children = set(
                    await session.scalars(select(MediaObject.id).where(MediaObject.parent_id.in_(works)))
                )
                if children:
                    children |= set(
                        await session.scalars(select(season.id).where(season.parent_id.in_(children)))
                    )
        found = frozenset(works | children | kept_kinds)
        if len(self._cache) > 500:
            self._cache.clear()
        self._cache[user] = (time.monotonic(), found)
        return found

    async def hidden(self, viewer: Principal | UUID | None) -> frozenset[UUID]:
        """The titles left out of the lists — those kept from the viewer, unless its master chose to show
        them locked."""
        restrictions = await self.restrictions(viewer)
        if restrictions is None or restrictions.mode in ("lock", "show"):  # 432: shown, a padlock
            return frozenset()
        return await self.blocked(viewer)

    async def mark(self, viewer: Principal | UUID | None, cards: list[Any]) -> list[Any]:
        """Cards (pydantic models with ``id`` and ``locked``) of titles kept from the viewer, shown locked —
        issue 434: and each card's age rating (``age``, the strictest of its ratings), for its badge."""
        blocked = await self.blocked(viewer)
        restrictions = await self.restrictions(viewer) if blocked else None
        flag = "kept" if restrictions is not None and restrictions.mode == "show" else "locked"
        aged = [c for c in cards if "age" in type(c).model_fields]
        ages = await self.ages([c.id for c in aged], unrated=-1, viewer=viewer) if aged else {}
        if not blocked and not ages:
            return cards
        out = []
        for card in cards:
            update: dict[str, Any] = {}
            if card.id in blocked and flag in type(card).model_fields:
                update[flag] = True  # 432: blurred with a padlock (« lock »), or a padlock only (« show »)
            if card.id in ages and "age" in type(card).model_fields:
                update["age"] = ages[card.id]
            out.append(card.model_copy(update=update) if update else card)
        return out

    async def rated_ages(self) -> dict[UUID, int | None]:
        """Issue 437: the strictest age of every title of a rated kind (``None``: unrated) — shared by every
        member, kept for a while."""
        country = await self.country()
        order = await self.rating_order()
        also = await self.also_countries()
        if (
            self._ages is not None
            and self._ages[1] == country
            and time.monotonic() - self._ages[0] < AGES_CACHE_S
        ):
            return self._ages[2]
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(
                        MediaObject.id, ObjectMetadata.data, MediaObject.effective["content_rating"].astext
                    )
                    .outerjoin(
                        ObjectMetadata,
                        (ObjectMetadata.object_id == MediaObject.id) & (ObjectMetadata.status == "found"),
                    )
                    .where(MediaObject.kind.in_(RATED))
                )
            ).all()
        out: dict[UUID, int | None] = {}
        for object_id, data, server in rows:
            age = title_age(data, server, country, order, also)
            known = out.get(object_id)
            out[object_id] = age if known is None else known if age is None else max(age, known)
        self._ages = (time.monotonic(), country, out)
        return out

    async def age_clause(self, viewer: Principal | UUID | None, age: str, *, unrated: bool = True) -> Any:
        """Issue 437: the catalog's age filter as a clause — the titles up to an age (``"12"``), or those
        this viewer may open (``"mine"``: none kept from it); unrated titles kept or left out. ``None``: no
        title to leave out."""
        if age not in AGE_FILTERS:
            return None
        ages = await self.rated_ages()
        clauses = []
        if age == "mine":
            if blocked := await self.blocked(viewer):
                clauses.append(excluded(MediaObject.id, blocked))
        else:
            limit = int(age)  # 18: every age
            if limit < 18 and (over := frozenset(i for i, a in ages.items() if a is not None and a > limit)):
                clauses.append(excluded(MediaObject.id, over))
        if not unrated:
            rated = [i for i, a in ages.items() if a is not None]
            clauses.append(MediaObject.id == any_(literal(rated, ARRAY(Uuid()))))
        return and_(*clauses) if clauses else None

    async def ages(
        self, ids: Iterable[UUID], *, unrated: int | None = None, viewer: Principal | UUID | None = None
    ) -> dict[UUID, int]:
        """Issue 434: the strictest age each title's ratings stand for — an unrated one left out, or given
        ``unrated`` (« ? » on its badge); unknown ids left out."""
        wanted = list(dict.fromkeys(ids))
        if not wanted:
            return {}
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(
                        MediaObject.id, ObjectMetadata.data, MediaObject.effective["content_rating"].astext
                    )
                    .outerjoin(
                        ObjectMetadata,
                        (ObjectMetadata.object_id == MediaObject.id) & (ObjectMetadata.status == "found"),
                    )
                    .where(MediaObject.id.in_(wanted))
                )
            ).all()
        out: dict[UUID, int] = {}
        country = await self.country()
        order = await self.rating_order()
        also = await self.countries_for(viewer)
        blend = await self.blend_for(viewer)
        for object_id, data, server in rows:
            age = title_age(data, server, country, order, also, blend)
            if age is not None:
                out[object_id] = max(age, out.get(object_id, age))
            elif unrated is not None and object_id not in out:
                out[object_id] = unrated
        return out

    async def screen_today(self, viewer: Principal | UUID | None) -> tuple[int, int] | None:
        """032: ``(minutes used today, minutes allowed a day)`` in the portal's player and reader, for a
        profile its master gave a screen time — ``None`` otherwise. The day is the economy's."""
        restrictions = await self.restrictions_any(viewer)
        user = viewer_of(viewer)
        if restrictions is None or user is None:
            return None
        start = await self._day_start()
        allowed = restrictions.minutes_on(start.date())  # 432: the weekly plan's, and today's extra minutes
        if allowed is None:
            return None
        return await self._used(user, start, restrictions.screen_scope), allowed

    async def screen_now(self, viewer: Principal | UUID | None) -> dict[str, Any] | None:
        """Issue 432: the profile's screen time now — the day's (``used``/``allowed``), whether it may watch
        at this hour (``open``), the span it is in with that span's use, today's spans and the next one."""
        restrictions = await self.restrictions_any(viewer)
        user = viewer_of(viewer)
        if restrictions is None or user is None:
            return None
        start = await self._day_start()
        now = datetime.now(start.tzinfo)
        allowed = restrictions.minutes_on(start.date())
        spans = restrictions.slots_on(now.weekday())
        if allowed is None and not spans and restrictions.hours is None:
            return None
        is_open, slot = restrictions.window(now)
        scope = restrictions.screen_scope
        used = await self._used(user, start, scope)
        current = None
        if slot is not None:
            since = start.replace(hour=int(slot.start[:2]), minute=int(slot.start[3:]))
            current = {
                "start": slot.start,
                "end": slot.end,
                "used": await self._used(user, since, scope),
                "allowed": restrictions.slot_minutes(slot, start.date()),
            }
        clock = now.strftime("%H:%M")
        upcoming = next((span for span in spans if span.start > clock), None)
        return {
            "used": used,
            "allowed": allowed,
            "open": is_open,
            "slot": current,
            "slots": [{"start": s.start, "end": s.end, "minutes": s.minutes} for s in spans],
            "next": {"start": upcoming.start, "end": upcoming.end} if upcoming else None,
            "hours": list(restrictions.hours) if restrictions.hours and not spans else None,
            "scope": scope,
        }

    async def beat(self, viewer: Principal | UUID | None) -> bool:
        """Issue 439: one more minute on the portal for a profile whose master counts all of Portalab — one
        a minute however often it comes; ``False`` for anyone else (nothing kept)."""
        restrictions = await self.restrictions_any(viewer)
        user = viewer_of(viewer)
        if restrictions is None or user is None or restrictions.screen_scope != "portal":
            return False
        minute = datetime.now(UTC).replace(second=0, microsecond=0)
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                pg_insert(ScreenBeat).values(user_id=user, minute=minute).on_conflict_do_nothing()
            )
            await uow.session.execute(
                delete(ScreenBeat).where(ScreenBeat.user_id == user, ScreenBeat.minute < minute - BEATS_KEPT)
            )
        return True

    async def _used(self, user: UUID, since: datetime, scope: str = "media") -> int:
        """Minutes watched, read or played in the portal since then (ended and running sittings) — issue
        439: or, all of Portalab counting, every minute on the portal or in a sitting (each minute once)."""
        if scope == "portal":
            return await self._on_portal(user, since)
        async with self.database.session() as session:
            ended = await session.scalar(
                select(func.coalesce(func.sum(Activity.watched_s), 0.0)).where(
                    Activity.user_id == user, Activity.stopped_at >= since
                )
            )
            running = await session.scalar(
                select(
                    func.coalesce(
                        func.sum(
                            PlaybackSession.max_position_s
                            - func.coalesce(PlaybackSession.start_position_s, 0.0)
                        ),
                        0.0,
                    )
                ).where(
                    PlaybackSession.played_by == user,
                    PlaybackSession.ended.is_(False),
                    PlaybackSession.started_at >= since,
                )
            )
        return int((float(ended or 0) + max(0.0, float(running or 0))) // 60)

    async def _on_portal(self, user: UUID, since: datetime) -> int:
        """Issue 439: the minutes since then on the portal (its tab in view) or in a sitting elsewhere (a
        film on the TV's Plex) — a film in the portal's player counts once, not on both counts."""
        async with self.database.session() as session:
            beats = await session.scalars(
                select(ScreenBeat.minute).where(ScreenBeat.user_id == user, ScreenBeat.minute >= since)
            )
            minutes = {beat.astimezone(UTC).replace(second=0, microsecond=0) for beat in beats}
            ended = await session.execute(
                select(Activity.started_at, Activity.stopped_at).where(
                    Activity.user_id == user, Activity.stopped_at >= since
                )
            )
            running = await session.execute(
                select(PlaybackSession.started_at, PlaybackSession.updated_at).where(
                    PlaybackSession.played_by == user,
                    PlaybackSession.ended.is_(False),
                    PlaybackSession.started_at >= since,
                )
            )
            sittings: list[tuple[datetime, datetime | None]] = [
                (start, stop) for start, stop in ended.tuples().all()
            ] + [(start, stop) for start, stop in running.tuples().all()]
        floor = since.astimezone(UTC)
        for start, stop in sittings:
            if stop is None:
                continue
            moment = max(start, floor).astimezone(UTC).replace(second=0, microsecond=0)
            last = min(stop.astimezone(UTC), moment + timedelta(days=1))
            while moment < last:
                minutes.add(moment)
                moment += MINUTE
        return len(minutes)

    async def check_screen(self, viewer: Principal | UUID | None) -> None:
        """Refuse to open a title once the profile's screen time of the day is spent — 432: or outside the
        spans (hours) its master set, or once the span's own time is spent."""
        now = await self.screen_now(viewer)
        if now is None:
            return
        if not now["open"]:
            hours = now["hours"] or ([now["next"]["start"], now["next"]["end"]] if now["next"] else None)
            raise ScreenTimeUp(
                "This profile may not watch at this hour.",
                extensions={"reason": "hours", "hours": hours, "next": now["next"], "slots": now["slots"]},
            )
        slot = now["slot"]
        if slot is not None and slot["allowed"] is not None and slot["used"] >= slot["allowed"]:
            raise ScreenTimeUp(
                "This profile's screen time for this span is spent.",
                extensions={
                    "reason": "slot",
                    "used": slot["used"],
                    "allowed": slot["allowed"],
                    "hours": [slot["start"], slot["end"]],
                    "next": now["next"],
                },
            )
        if now["allowed"] is not None and now["used"] >= now["allowed"]:
            raise ScreenTimeUp(
                "This profile's screen time for today is spent.",
                extensions={"used": now["used"], "allowed": now["allowed"]},
            )

    async def restrictions_any(self, viewer: Principal | UUID | None) -> Restrictions | None:
        """A profile's restrictions, whatever they restrict."""
        user, household = viewer_of(viewer), self._household()
        if user is None or household is None:
            return None
        return await household.restrictions_of(user)

    async def _day_start(self) -> datetime:
        zone = ZoneInfo("UTC")
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                zone = ZoneInfo(str((await providers[0].provider.get("economy.timezone")).value or "UTC"))
        except Exception:  # noqa: S110 — the day falls back to UTC's
            pass
        now = datetime.now(zone)
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    async def requestable(
        self, viewer: Principal | UUID | None, items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """032: the request service's titles (TMDB's shelves and search) for a restricted profile — one in the
        library follows its lock; one outside it has no known rating: unrated (left out when the profile opens
        rated titles only, or films and series are kept from it). Locked ones carry ``locked`` (lock mode)."""
        restrictions = await self.restrictions(viewer)
        if restrictions is None:
            return items
        blocked = await self.blocked(viewer)
        kept_kinds = restrictions.kinds
        outside = await self._rate_outside(restrictions, [i for i in items if _id_of(i, "object_id") is None])
        out: list[dict[str, Any]] = []
        for item in items:
            object_id = _id_of(item, "object_id")
            kind = "movie" if item.get("kind") == "movie" else "series"
            kept = (
                object_id in blocked
                if object_id is not None
                else kind in kept_kinds or outside.get(id(item), not restrictions.allow_unrated)
            )
            if not kept:
                out.append(item)
            elif restrictions.mode in ("lock", "show"):
                out.append({**item, "locked": True})
        return out

    async def _rate_outside(self, restrictions: Restrictions, items: list[dict[str, Any]]) -> dict[int, bool]:
        """Issue 478: titles outside the library (the request service's shelves and search) rated as the
        library's are — their ratings looked up once on the metadata provider (TMDB), then held to the
        profile's age, countries, reading and warnings, and its kept-out genres and keywords. ``id(item)`` →
        kept; a title the provider does not know is left out of the answer (unrated: as before)."""
        briefs = self.briefs
        if briefs is None or not items:
            return {}
        country = await self.country()
        order = await self.rating_order()
        also = (
            restrictions.rating_countries
            if restrictions.rating_countries is not None
            else await self.also_countries()
        )
        avoid = restrictions.avoid_warnings
        cnc = await self.cnc_warned() if "cnc" in avoid else None
        gate = asyncio.Semaphore(8)

        async def rate(item: dict[str, Any]) -> tuple[int, bool | None]:
            kind = "movie" if item.get("kind") == "movie" else "series"
            tmdb = str(item.get("tmdb_id") or "")
            if not tmdb.isdigit():
                return id(item), None
            async with gate:  # (a lookup that fails is remembered as nothing known: unrated)
                brief = await briefs.brief(kind, {"tmdb": tmdb}, str(item.get("title") or tmdb), None)
            data = (brief or {}).get("rated")
            if not data:
                return id(item), None
            age = title_age(data, None, country, order, also, restrictions.rating_blend)
            if age is None:
                return id(item), None
            kept = not restrictions.allows_age(age) or bool(avoid and avoid & self._warnings(data, cnc))
            if not kept and restrictions.genres:
                kept = any(genre_key(str(g)) in restrictions.genres for g in data.get("genres") or [])
            if not kept and restrictions.keywords:
                kept = keyword_hit(data.get("keywords"), restrictions.keywords)
            return id(item), kept

        rated = await asyncio.gather(*(rate(item) for item in items))
        return {key: kept for key, kept in rated if kept is not None}

    async def keywords(self, typed: str, limit: int = 20) -> list[str]:
        """Issue 478: the library's metadata keywords containing what a master types (« drug » → « drug
        abuse », « drug addiction »…), the most used first — to keep a profile from them."""
        wanted = typed.strip().casefold()[:60]
        if len(wanted) < 2:
            return []
        item = func.jsonb_array_elements_text(ObjectMetadata.data["keywords"]).alias("item")
        value: Any = literal_column("item")
        async with self.database.session() as session:
            rows = await session.execute(
                select(func.min(value), func.count())
                .select_from(ObjectMetadata)
                .join(item, literal(True))
                .where(
                    ObjectMetadata.status == "found",
                    func.jsonb_typeof(ObjectMetadata.data["keywords"]) == "array",
                    func.lower(value).contains(wanted, autoescape=True),
                )
                .group_by(func.lower(value))
                .order_by(func.count().desc(), func.min(value))
                .limit(max(1, min(limit, 50)))
            )
            return [str(word) for word, _ in rows.all()]

    def forget(self) -> None:
        self._cache.clear()
        # issue 478: the administrator's choices and the CNC's warnings read again too
        self._order = self._also = self._warned = None

    async def check(
        self, viewer: Principal | UUID | None, object_id: UUID, title: str = "", *, viewing: bool = False
    ) -> None:
        """Refuse one title the viewer may not open, telling enough for « Ask for access » — issue 432: its
        page (``viewing``) stays open to a profile whose master shows such titles (« show »)."""
        kept = await self.kept(viewer, object_id, title)
        if kept is None:
            return
        if viewing and kept.pop("shown", False):
            return
        kept.pop("shown", None)
        raise Restricted("This title is kept from this profile.", extensions=kept)

    async def kept(
        self, viewer: Principal | UUID | None, object_id: UUID, title: str = ""
    ) -> dict[str, Any] | None:
        """Why a title is kept from a profile, and whether it is still shown (``shown``: its master's
        « show » choice) — ``None``: it is not kept."""
        if object_id not in await self.blocked(viewer):
            return None
        found = await self.rating(object_id, viewer)  # issue 478: by its own countries
        restrictions = await self.restrictions(viewer)
        reason = await self._reason(object_id, restrictions, found["age"])
        # issue 478: of its age, but carrying a warning its master keeps it from
        warned = sorted(
            set(found.get("warnings") or []) & (restrictions.avoid_warnings if restrictions else set())
        )
        if (
            warned
            and reason in ("age", "unrated")
            and restrictions is not None
            and restrictions.allows_age(found["age"])
        ):
            reason = "warning"
        return {
            "warnings": warned if reason == "warning" else [],
            "object_id": str(object_id),
            "name": title,
            "rating": f"{found['age']}+" if found["age"] is not None else None,
            # why: its age, no rating yet, a genre, a kind of content or the title kept out by hand
            "reason": reason,
            # the master's own choices (a title, a kind) are not asked again title by title
            "can_ask": (restrictions is None or restrictions.requests) and reason in ASKABLE,
            "shown": restrictions is not None and restrictions.mode == "show",
        }

    async def _reason(self, object_id: UUID, restrictions: Restrictions | None, age: int | None) -> str:
        """Why a title is kept from a profile: ``title``, ``type``, ``genre``, ``keyword``, ``unrated`` or
        ``age``."""
        if restrictions is None:
            return "age"
        async with self.database.session() as session:
            chain: list[tuple[UUID, str]] = []
            current: UUID | None = object_id
            for _ in range(3):
                if current is None:
                    break
                row = (
                    await session.execute(
                        select(MediaObject.parent_id, MediaObject.kind).where(MediaObject.id == current)
                    )
                ).one_or_none()
                if row is None:
                    break
                chain.append((current, str(row.kind)))
                current = row.parent_id
            if any(str(found) in restrictions.titles for found, _ in chain):
                return "title"
            if chain and chain[0][1] in restrictions.kinds:
                return "type"
            if restrictions.genres:
                tags = await session.scalars(
                    select(ObjectTag.value).where(
                        ObjectTag.tag_kind == "genre", ObjectTag.object_id.in_([found for found, _ in chain])
                    )
                )
                if any(genre_key(str(tag)) in restrictions.genres for tag in tags):
                    return "genre"
            if restrictions.keywords:  # issue 478: one of its keywords kept from the profile
                found_keywords = await session.scalars(
                    select(ObjectMetadata.data["keywords"]).where(
                        ObjectMetadata.object_id.in_([found for found, _ in chain]),
                        ObjectMetadata.status == "found",
                    )
                )
                if any(keyword_hit(words, restrictions.keywords) for words in found_keywords):
                    return "keyword"
        return "unrated" if age is None else "age"

    async def _rating(self, object_id: UUID) -> str | None:
        """The strictest age a title (or the series of an episode or a season) is rated for, as « 17+ »."""
        found = await self.rating(object_id)
        return f"{found['age']}+" if found["age"] is not None else None

    async def rating(self, object_id: UUID, viewer: Principal | UUID | None = None) -> dict[str, Any]:
        """032: a title's age ratings, source by source (TMDB's countries, the media server), and the
        strictest age they stand for — an episode or a season answers with its series' when it has none."""
        async with self.database.session() as session:
            current: UUID | None = object_id
            for _ in range(3):
                if current is None:
                    break
                row = (
                    await session.execute(
                        select(
                            MediaObject.parent_id,
                            ObjectMetadata.data,
                            MediaObject.effective["content_rating"].astext,
                        )
                        .outerjoin(
                            ObjectMetadata,
                            (ObjectMetadata.object_id == MediaObject.id) & (ObjectMetadata.status == "found"),
                        )
                        .where(MediaObject.id == current)
                    )
                ).one_or_none()
                if row is None:
                    break
                parent, data, server = row
                sources = labelled(data, server)
                if sources:
                    country = await self.country()
                    order = await self.rating_order()
                    also = await self.countries_for(viewer)
                    blend = await self.blend_for(viewer)
                    return {
                        "age": title_age(data, server, country, order, also, blend),
                        "country": country,
                        "ratings": [{"source": s, "value": v} for s, v in own_first(sources, country)],
                        **(await self._details(current, data, server, country, also, blend)),
                    }
                current = parent
        return {"age": None, "ratings": []}

    async def _details(
        self,
        object_id: UUID,
        data: Mapping[str, Any] | None,
        server: str | None,
        country: str | None,
        also: tuple[str, ...] = (),
        blend: str = "strictest",
    ) -> dict[str, Any]:
        """Issue 478: a title's ratings in full — which release its age follows, every release's rating,
        and (for a film) the CNC's decision."""
        releases = [r for r in (data or {}).get("releases") or [] if isinstance(r, Mapping)]
        listed: list[dict[str, Any]] = [
            {
                "country": str(r.get("country") or ""),
                "type": str(r.get("type") or "cinema"),
                "certification": str(r.get("certification") or ""),
                "age": age_of(str(r.get("certification") or "")),
                "note": r.get("note"),
                "descriptors": [str(d) for d in r.get("descriptors") or []],
                "date": r.get("date"),
            }
            for r in releases
            if r.get("certification")
        ]
        basis = "other"
        tiers = order_of(await self.rating_order())
        if not tiers:
            basis = "strictest"
        elif country:
            local = country.upper()
            mine = {
                str(r["type"]) for r in listed if str(r["country"]).upper() == local and r["age"] is not None
            }
            basis = next((tier for tier in tiers if mine & set(TIERS[tier])), "other")
        # another country the administrator chose rates it stricter: that country sets the age
        abroad = None
        if also and country:
            order = await self.rating_order()
            own = country_age(data, server, country, order)
            own = own if own is not None else local_age(labelled(data, server), country)
            final = title_age(data, server, country, order, also)
            if final is not None and (own is None or final > own):
                certifications = (data or {}).get("certifications") or {}
                for other in also:
                    age = country_age(data, None, other, order)
                    if age is None and isinstance(certifications, Mapping) and certifications.get(other):
                        age = age_of(str(certifications[other]))
                    if age == final:
                        basis, abroad = "abroad", other
                        break
        cnc = None
        if self.cnc is not None and data and (data.get("title") or data.get("original_title")):
            year = str(data.get("release_date") or "")[:4]
            found = await self.cnc.find(
                [r.get("note") for r in listed if r["country"] == "FR"],
                [data.get("title"), data.get("original_title")],
                int(year) if year.isdigit() else None,
            )
            if found is not None:
                cnc = {
                    "visa": found.visa,
                    "decision": found.decision,
                    "warning": "avertissement" in found.decision.lower(),
                    "title": found.title,
                    "year": found.year,
                }
        if blend == "average":  # issue 478: its master reads it by the average of every country's rating
            basis, abroad = "average", None
        elif blend == "highest":  # or by the strictest of every country's: the country that sets it
            ages = _ages_by_country(data, server, country, await self.rating_order())
            if ages:
                top = max(ages.values())
                local = (country or "").upper()
                basis = "highest"
                abroad = local if ages.get(local) == top else next(c for c, a in ages.items() if a == top)
        warnings = warnings_of(data)
        if cnc is not None and cnc["warning"]:
            warnings.add("cnc")
        return {
            "basis": basis if listed or abroad or blend in ("average", "highest") else None,
            "basis_country": abroad,
            "releases": listed,
            "cnc": cnc,
            "warnings": sorted(warnings),
        }

    async def keep(self, viewer: Principal | UUID | None, items: Iterable[Any], key: str = "id") -> list[Any]:
        """The items (objects or mappings) whose ``key`` is a title the viewer's lists may show."""
        blocked = await self.hidden(viewer)
        items = list(items)
        if not blocked:
            return items
        return [item for item in items if _id_of(item, key) not in blocked]

    async def scrub(self, viewer: Principal | UUID | None, payload: Any) -> Any:
        """A response (mappings and lists, as JSON goes) without the entries naming a title kept from the
        viewer — for the many lists of titles a page or a widget draws."""
        blocked = await self.hidden(viewer)
        return _scrub(payload, {str(b) for b in blocked}) if blocked else payload


def _id_of(item: Any, key: str) -> UUID | None:
    raw = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(str(raw)) if raw is not None else None
    except ValueError:
        return None


def _names(item: dict[str, Any], blocked: set[str]) -> bool:
    return any(str(item.get(key)) in blocked for key in IDS if item.get(key) is not None)


def _scrub(payload: Any, blocked: set[str]) -> Any:
    if isinstance(payload, list):
        return [
            _scrub(item, blocked)
            for item in payload
            if not (isinstance(item, dict) and _names(item, blocked))
        ]
    if isinstance(payload, dict):
        return {key: _scrub(value, blocked) for key, value in payload.items()}
    return payload


class GatedWidget:
    """A media widget whose lists leave out what the viewer's age rating keeps from them."""

    def __init__(self, inner: Any, gate: TitleGate) -> None:
        self.inner = inner
        self.gate = gate
        if hasattr(inner, "title_gate"):  # issue 474: a widget drawing titles leaves out the hidden ones
            inner.title_gate = gate

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    async def load(self, principal: Principal, config: Any, ctx: Any) -> Any:
        payload = await self.inner.load(principal, config, ctx)
        data = getattr(payload, "data", None)
        if data is None or not await self.gate.hidden(principal):
            return payload
        return replace(payload, data=await self.gate.scrub(principal, dict(data)))


class GatedSearch:
    """The media search provider without the titles the viewer's age rating keeps from them."""

    def __init__(self, inner: Any, gate: TitleGate) -> None:
        self.inner = inner
        self.gate = gate

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    async def _visible(self, principal: Principal, items: Iterable[Any]) -> list[Any]:
        blocked = {str(b) for b in await self.gate.hidden(principal)}
        return [item for item in items if str(getattr(item, "id", "")) not in blocked]

    async def search(
        self, query: Any, principal: Principal, ctx: Any, *, limit: int, cursor: str | None
    ) -> Any:
        result = await self.inner.search(query, principal, ctx, limit=limit, cursor=cursor)
        if not await self.gate.hidden(principal):
            return result
        return replace(result, items=await self._visible(principal, result.items))

    async def suggestions(self, query: Any, principal: Principal, **options: Any) -> Any:
        return await self._visible(principal, await self.inner.suggestions(query, principal, **options))

    async def hydrate(self, ids: Any, principal: Principal) -> Any:
        return await self._visible(principal, await self.inner.hydrate(ids, principal))
