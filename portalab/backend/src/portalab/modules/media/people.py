"""#92 — the people behind the library's titles (``media.credits``): found by name — every word of the query,
in any order, a close spelling forgiven — and each with a page of their titles, by role (directed, wrote,
read, played in…). An episode or a season counts as its series, a track as its album."""

import asyncio
import logging
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, distinct, func, select
from sqlalchemy.orm import aliased

from portalab.capabilities.media import PEOPLE, PersonRecord, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.modules.media.matching import escaped, found, whole
from portalab.modules.media.models import Credit, MediaObject

# the order of a person's roles on their page
ROLES = ("director", "creator", "writer", "author", "narrator", "cast", "artist")

_parent = aliased(MediaObject)
_grandparent = aliased(MediaObject)
# the work a credit counts for: an episode's series, a season's series, a track's album, or the title itself
WORK = case(
    (MediaObject.kind == "episode", func.coalesce(_grandparent.id, _parent.id, MediaObject.id)),
    (MediaObject.kind.in_(("season", "track")), func.coalesce(_parent.id, MediaObject.id)),
    else_=MediaObject.id,
)


@dataclass(frozen=True, slots=True)
class PersonHit:
    name: str
    titles: int
    roles: tuple[str, ...]
    portrait: str | None


@dataclass(frozen=True, slots=True)
class PersonPage:
    name: str
    portrait: str | None
    roles: tuple[str, ...]
    works: dict[str, list[UUID]] = field(default_factory=dict)  # role → titles, the most recent first
    ref: str | None = None  # their id at the metadata provider (TMDB), the most often seen


def _credited(stmt: Any) -> Any:
    return (
        stmt.join(MediaObject, MediaObject.id == Credit.object_id)
        .outerjoin(_parent, _parent.id == MediaObject.parent_id)
        .outerjoin(_grandparent, _grandparent.id == _parent.parent_id)
        .where(MediaObject.status == "active")
    )


def _ordered(roles: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(roles), key=lambda r: ROLES.index(r) if r in ROLES else len(ROLES)))


class People:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def find(
        self,
        query_words: Sequence[str],
        phrase: str = "",
        *,
        limit: int,
        offset: int = 0,
        roles: Sequence[str] = (),
    ) -> list[PersonHit]:
        """The people every word names — the name as typed first (« chris o dowd »), then a name starting
        with it, the words as words, inside others, a close spelling; then the most credited."""
        if not query_words or sum(len(w) for w in query_words) < 3:
            return []
        text = phrase or " ".join(query_words)
        like = escaped(text)
        tier = func.min(
            case(
                (Credit.folded == text, 0),
                (Credit.folded.like(f"{like}%", escape="\\"), 1),
                (Credit.folded.like(f"% {like}%", escape="\\"), 2),
                (and_(*(whole(Credit.folded, word) for word in query_words)), 3),
                (and_(*(Credit.folded.contains(word, autoescape=True) for word in query_words)), 4),
                else_=5,
            )
        ).label("tier")
        titles = func.count(distinct(WORK)).label("titles")
        stmt = _credited(
            select(
                func.min(Credit.name).label("name"),
                titles,
                func.array_agg(distinct(Credit.role)).label("roles"),
                func.max(Credit.image).label("portrait"),
                tier,
            )
        ).where(*(found(Credit.folded, word) for word in query_words))
        if roles:
            stmt = stmt.where(Credit.role.in_(list(roles)))
        stmt = stmt.group_by(Credit.folded).order_by(tier, titles.desc(), func.min(Credit.name))
        async with self.database.session() as session:
            rows = (await session.execute(stmt.offset(offset).limit(limit))).all()
        return [
            PersonHit(name=row.name, titles=int(row.titles), roles=_ordered(row.roles), portrait=row.portrait)
            for row in rows
        ]

    async def page(self, name: str) -> PersonPage | None:
        """A person's titles by role — the same name however it is written (accents, apostrophes)."""
        stmt = _credited(
            select(
                func.min(Credit.name).label("name"),
                Credit.role,
                WORK.label("work"),
                func.max(Credit.image).label("portrait"),
                func.max(Credit.ref).label("ref"),
            )
        ).where(Credit.folded == func.media.search_fold(name.strip()[:200]))
        stmt = stmt.group_by(Credit.role, WORK)
        async with self.database.session() as session:
            rows = (await session.execute(stmt)).all()
            if not rows:
                return None
            works = {row.work for row in rows}
            found = await session.execute(
                select(MediaObject.id, MediaObject.year, MediaObject.sort_title).where(
                    MediaObject.id.in_(works), MediaObject.status == "active"
                )
            )
            order = {
                object_id: (-(year or 0), sort_title or "") for object_id, year, sort_title in found.all()
            }
        by_role: dict[str, list[UUID]] = {}
        for row in rows:
            if row.work in order:
                by_role.setdefault(row.role, []).append(row.work)
        for role, titles in by_role.items():
            by_role[role] = sorted(dict.fromkeys(titles), key=lambda t: order[t])
        names = sorted({row.name for row in rows}, key=lambda n: (n.lower() == n, n))  # capitalised first
        portrait = next((row.portrait for row in rows if row.portrait), None)
        roles = _ordered(list(by_role))
        refs = Counter(row.ref for row in rows if row.ref)
        return PersonPage(
            name=names[0],
            portrait=portrait,
            roles=roles,
            works={role: by_role[role] for role in roles},
            ref=refs.most_common(1)[0][0] if refs else None,
        )


log = logging.getLogger(__name__)
# whose word comes first when services tell different things (the richest sources first)
PREFERENCE = ("tmdb", "seerr", "jellyfin", "emby", "plex", "grimmory", "hardcover")
BOOKS_FIRST = ("grimmory", "hardcover")  # an author or a narrator: the book services know them best
PROFILE_TTL = 6 * 3600
TIMEOUT = 15


@dataclass(frozen=True, slots=True)
class Source:
    service_id: str
    connector: str
    name: str


@dataclass(frozen=True, slots=True)
class Profile:
    """What the configured services know of a person, merged: each field from the first service (in
    ``PREFERENCE`` order) that knows it; the filmography from the one that lists the most titles."""

    record: PersonRecord
    portrait: tuple[str, str] | None  # (service id, its reference)
    sources: tuple[Source, ...]
    books: str | None = None  # issue 362: the service whose books they are (their covers fetched there)


class Profiles:
    """#92 — every service providing ``media.people`` (TMDB, Seerr, Jellyfin, Grimmory…) asked at once;
    whichever are configured, the page is as rich as they make it — and still there with none."""

    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities
        self._kept: dict[tuple[str, str, str, str], tuple[float, Profile | None]] = {}

    def _providers(self, books: bool = False) -> list[tuple[Source, Any]]:
        try:
            registrations = self.capabilities.system_providers(PEOPLE)
        except Exception:
            return []
        found = []
        for registration in registrations:
            meta = registration.metadata or {}
            connector = str(meta.get("connector") or "")
            source = Source(registration.instance_ref, connector, str(meta.get("name") or connector))
            found.append((source, registration.provider))
        order = (*BOOKS_FIRST, *PREFERENCE) if books else PREFERENCE
        rank: dict[str, int] = {}
        for key in order:
            rank.setdefault(key, len(rank))
        return sorted(found, key=lambda pair: rank.get(pair[0].connector, len(rank)))

    async def _ask(self, source: Source, provider: Any, name: str, ids: Any, language: str) -> Any:
        try:
            return unwrap(await asyncio.wait_for(provider.person(name, ids, language), timeout=TIMEOUT))
        except Exception as exc:
            log.info("person lookup failed on %s: %s", source.connector, type(exc).__name__)
            return None

    async def profile(
        self, name: str, ids: dict[str, str], language: str, *, books: bool = False
    ) -> Profile | None:
        """``books``: someone the library credits on books only (an author, a narrator)."""
        key = (name.casefold(), ids.get("tmdb", ""), language, str(books))
        kept = self._kept.get(key)
        now = time.monotonic()
        if kept is not None and now - kept[0] < PROFILE_TTL:
            return kept[1]
        providers = self._providers(books)
        if not providers:
            return None
        answers = await asyncio.gather(*(self._ask(s, p, name, ids, language) for s, p in providers))
        found = [
            (source, record)
            for (source, _), record in zip(providers, answers, strict=True)
            if isinstance(record, PersonRecord)
        ]
        merged = _merge(name, found, books) if found else None
        if len(self._kept) > 500:
            self._kept.clear()
        self._kept[key] = (now, merged)
        return merged

    async def portrait(self, service_id: str, ref: str, size: str) -> bytes:
        for source, provider in self._providers():
            if source.service_id == service_id:
                data: bytes = unwrap(await asyncio.wait_for(provider.portrait(ref, size), timeout=TIMEOUT))
                return data
        raise LookupError("no such people source")


def _merge(name: str, found: Sequence[tuple[Source, PersonRecord]], books: bool = False) -> Profile:
    def first(field_name: str) -> Any:
        return next((getattr(r, field_name) for _, r in found if getattr(r, field_name)), None)

    # the films and series (every part they took, whatever it was) from the service listing the most of
    # them; the books (issue 362) from the first book database knowing them
    films = [(s, [c for c in r.credits if c.kind != "book"]) for s, r in found]
    richest = max(films, key=lambda pair: len(pair[1]))[1]
    shelf = next(((s, [c for c in r.credits if c.kind == "book"]) for s, r in found if _has_books(r)), None)
    ids: dict[str, str] = {}
    for _, record in found:
        for scheme, value in record.ids.items():
            ids.setdefault(scheme, value)
    portrait = next(((s.service_id, r.portrait) for s, r in found if r.portrait), None)
    record = PersonRecord(
        ids=ids,
        name=first("name") or name,
        biography=first("biography"),
        birthday=first("birthday"),
        deathday=first("deathday"),
        place_of_birth=first("place_of_birth"),
        known_for="Writing" if books else first("known_for"),
        portrait=None,
        popularity=first("popularity"),
        also_known_as=first("also_known_as") or (),
        credits=(*(shelf[1] if shelf else ()), *richest),
    )
    return Profile(
        record=record,
        portrait=portrait,
        sources=tuple(s for s, _ in found),
        books=shelf[0].service_id if shelf else None,
    )


def _has_books(record: PersonRecord) -> bool:
    return any(credit.kind == "book" for credit in record.credits)
