"""Search integration (T028; 008 SDK): ``SearchProvider(kind="media")`` with ``subtype`` (#92: film,
series, book, audiobook…), ``genre``, ``year`` and ``availability`` facets, scoped by ``media.read`` at the
source, plus the ``media:`` / ``tmdb:``… ``ObjectResolver`` and the palette actions ``media.open`` /
``media.request``."""

import time
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import Select, case, func, select

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search import (
    ActionDef,
    FacetDef,
    ObjectRef,
    ParsedQuery,
    ProviderResult,
    SearchItem,
)
from portalab.capabilities.search.fts import decode_cursor, encode_cursor, snippet
from portalab.core.authz_port import Authorizer, Principal
from portalab.modules.media.catalog import CatalogPort, CatalogQuery
from portalab.modules.media.databases import interleave
from portalab.modules.media.matching import (
    credited,
    fold,
    matching,
    metadata_people,
    relevance,
    series_order,
    words,
)
from portalab.modules.media.models import MediaObject, MediaRequest, ObjectTag
from portalab.modules.media.people import ROLES, People
from portalab.modules.media.permissions import MEDIA_READ, MEDIA_REQUEST

# #67: among equally relevant titles, the order of the kinds (films and series before books and tracks)
KIND_ORDER = ("movie", "series", "game", "book", "audiobook", "album", "live", "season", "episode", "track")

ACTIONS = (
    ActionDef(
        "media.open", "media:action.open", MEDIA_READ, route="/media", keywords=("media", "films", "library")
    ),
    ActionDef(
        "media.request", "media:action.request", MEDIA_REQUEST, route="/media/requests", keywords=("request",)
    ),
)


class MediaSearchProvider:
    kind = "media"
    label_key = "search.kind.media"
    required_permission = MEDIA_READ

    def __init__(self, query: CatalogQuery, authorizer: Authorizer) -> None:
        self.query = query
        self.authorizer = authorizer

    def facets(self) -> Sequence[FacetDef]:
        return (
            FacetDef("subtype", "search.facet.subtype"),
            FacetDef("genre", "search.facet.genre", kind="text"),
            FacetDef("year", "search.facet.year", kind="text"),
            FacetDef("availability", "search.facet.availability", values=("available", "unavailable")),
        )

    async def _extras(
        self, rows: Sequence[MediaObject], query_words: Sequence[str] = ()
    ) -> dict[UUID, dict[str, str]]:
        """#67: what a result shows beside its title — the poster, the first genres and the title's state
        (available, requested — a request in progress — or not available); #92: and who, among its people,
        the query found (``person`` and its ``role``: « by Robin Hobb », « with Chris O'Dowd »)."""
        from portalab.modules.media.providers.insight_widgets import posters

        ids = [row.id for row in rows]
        if not ids:
            return {}
        images = await posters(self.query.database, ids)
        async with self.query.database.session() as session:
            tags = (
                await session.execute(
                    select(ObjectTag.object_id, ObjectTag.value).where(
                        ObjectTag.object_id.in_(ids), ObjectTag.tag_kind == "genre"
                    )
                )
            ).all()
            asked = set(
                (
                    await session.execute(
                        select(MediaRequest.object_id).where(
                            MediaRequest.object_id.in_(ids),
                            MediaRequest.state.in_(("pending", "approved", "processing")),
                        )
                    )
                ).scalars()
            )
            provider_people = await metadata_people(session, ids) if query_words else {}
        genres: dict[UUID, list[str]] = {}
        for object_id, value in tags:
            genres.setdefault(object_id, []).append(str(value))
        out: dict[UUID, dict[str, str]] = {}
        for row in rows:
            state = "available" if row.available else "requested" if row.id in asked else "unavailable"
            extra = {"status": state}
            if images.get(row.id):
                extra["image"] = str(images[row.id])
            if genres.get(row.id):
                extra["genres"] = ", ".join(sorted(genres[row.id])[:3])
            found = credited(row, query_words, provider_people.get(row.id, ())) if query_words else None
            if found:
                extra["person"], extra["role"] = found
            out[row.id] = extra
        return out

    def _item(
        self,
        row: MediaObject,
        query: ParsedQuery,
        score: float = 0.0,
        extra: dict[str, str] | None = None,
    ) -> SearchItem:
        overview = str((row.effective or {}).get("overview") or row.title)
        return SearchItem(
            kind=self.kind,
            id=str(row.id),
            title=f"{row.title} ({row.year})" if row.year else row.title,
            url_ref=f"/media/{row.id}",
            snippet=snippet(overview, query.terms),
            score=score,
            facets={
                "type": row.kind,
                "availability": "available" if row.available else "unavailable",
                **({"year": str(row.year)} if row.year else {}),
                **(extra or {}),
            },
        )

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        if not await self.authorizer.is_allowed(principal, MEDIA_READ):
            return ProviderResult()
        query_words = words(query.text)
        stmt = self._filtered(query, query_words)
        offset = decode_cursor(cursor)
        async with self.query.database.session() as session:
            rows = (
                (
                    await session.execute(
                        stmt.order_by(*self._relevance(query_words, fold(query.text)))
                        .offset(offset)
                        .limit(limit + 1)
                    )
                )
                .scalars()
                .all()
            )
            # #92: the counts cover every match (not the first page alone); a subtype's own count ignores
            # the subtype chosen, so the others stay offered
            counted = self._filtered(query, query_words, subtype=False).subquery()
            by_kind = (
                await session.execute(select(counted.c.kind, func.count()).group_by(counted.c.kind))
            ).all()
            by_state = (
                await session.execute(select(counted.c.available, func.count()).group_by(counted.c.available))
            ).all()
        facets: dict[str, dict[str, int]] = {
            "subtype": {str(kind): int(count) for kind, count in by_kind},
            "availability": {
                "available" if available else "unavailable": int(count) for available, count in by_state
            },
        }
        extras = await self._extras(rows[:limit], query_words)
        return ProviderResult(
            items=[self._item(row, query, 1.0, extras.get(row.id)) for row in rows[:limit]],
            next_cursor=encode_cursor(offset + limit) if len(rows) > limit else None,
            facets=facets,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    @staticmethod
    def _filtered(query: ParsedQuery, query_words: Sequence[str], *, subtype: bool = True) -> Select[Any]:
        stmt = select(MediaObject).where(MediaObject.status == "active")
        filters = query.filters
        if subtype and filters.get("subtype"):
            stmt = stmt.where(MediaObject.kind.in_(filters["subtype"]))
        if filters.get("availability"):
            wanted = set(filters["availability"])
            if wanted == {"available"} or wanted == {"unavailable"}:
                stmt = stmt.where(MediaObject.available.is_("available" in wanted))
        if filters.get("year"):
            years = [int(y) for y in filters["year"] if str(y).isdigit()]
            stmt = stmt.where(MediaObject.year.in_(years))
        if filters.get("genre"):
            stmt = stmt.where(
                MediaObject.id.in_(
                    select(ObjectTag.object_id).where(
                        ObjectTag.tag_kind == "genre", ObjectTag.value.in_(list(filters["genre"]))
                    )
                )
            )
        if query_words:
            stmt = stmt.where(matching(query_words))
        return stmt

    async def suggestions(
        self, query: ParsedQuery, principal: Principal, *, per_type: int = 2
    ) -> Sequence[SearchItem]:
        """#67: the header's suggestions — the most relevant titles of *each* type (films, games, books…),
        not the first page alone (four games and six films filled it before any book)."""
        query_words = words(query.text)
        if not query_words or not await self.authorizer.is_allowed(principal, MEDIA_READ):
            return []
        order = self._relevance(query_words, fold(query.text))
        ranked = (
            select(
                MediaObject.id.label("id"),
                func.row_number().over(partition_by=MediaObject.kind, order_by=order).label("place"),
                order[0].label("tier"),
            )
            .where(MediaObject.status == "active")
            .where(matching(query_words))
            .subquery()
        )
        async with self.query.database.session() as session:
            picked = (
                await session.execute(
                    select(ranked.c.id, ranked.c.tier, ranked.c.place).where(ranked.c.place <= per_type)
                )
            ).all()
            if not picked:
                return []
            rows = {
                row.id: row
                for row in (
                    await session.execute(
                        select(MediaObject).where(MediaObject.id.in_([p.id for p in picked]))
                    )
                ).scalars()
            }
        best = sorted(picked, key=lambda p: (p.place, p.tier))  # each type's best first, by relevance
        objects = [rows[p.id] for p in best if p.id in rows]
        extras = await self._extras(objects, query_words)
        return [self._item(row, query, 1.0, extras.get(row.id)) for row in objects]

    @staticmethod
    def _relevance(query_words: Sequence[str], phrase: str = "") -> list[Any]:
        """#67: the most relevant first — the exact title, a title starting with the words, a word of the
        title starting with them, the words all in the title; #92: then the words all found elsewhere (its
        series, its people), then a close spelling; then films and series before books…; then a series in
        its order; then A to Z. (Sorting A to Z alone put « 095 [An +001] Star Wars… » books before every
        « Star Wars » film.)"""
        kind_rank = case(
            *((MediaObject.kind == kind, index) for index, kind in enumerate(KIND_ORDER)),
            else_=len(KIND_ORDER),
        )
        if not query_words:
            return [kind_rank, MediaObject.sort_title]
        return [relevance(query_words, phrase), kind_rank, *series_order(), MediaObject.sort_title]

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        if not await self.authorizer.is_allowed(principal, MEDIA_READ):
            return []
        wanted = []
        for value in ids:
            try:
                wanted.append(UUID(value))
            except ValueError:
                continue
        if not wanted:
            return []
        async with self.query.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(MediaObject).where(MediaObject.id.in_(wanted), MediaObject.status == "active")
                    )
                )
                .scalars()
                .all()
            )
        empty = ParsedQuery(text="", normalized="", terms=())
        extras = await self._extras(rows)
        return [self._item(row, empty, extra=extras.get(row.id)) for row in rows]


class PeopleSearchProvider:
    """#92: the people behind the library's titles — actors, directors, writers, authors, narrators — each
    opening their page of titles; a section of its own in the search and its suggestions."""

    kind = "person"
    label_key = "search.kind.person"
    required_permission = MEDIA_READ

    def __init__(self, people: People, authorizer: Authorizer) -> None:
        self.people = people
        self.authorizer = authorizer

    def facets(self) -> Sequence[FacetDef]:
        return (FacetDef("role", "search.facet.role", values=ROLES),)

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        if not await self.authorizer.is_allowed(principal, MEDIA_READ):
            return ProviderResult()
        offset = decode_cursor(cursor)
        hits = await self.people.find(
            words(query.text),
            fold(query.text),
            limit=limit + 1,
            offset=offset,
            roles=query.filters.get("role") or (),
        )
        counts: dict[str, int] = {}
        for hit in hits[:limit]:
            for role in hit.roles:
                counts[role] = counts.get(role, 0) + 1
        return ProviderResult(
            items=[
                SearchItem(
                    kind=self.kind,
                    id=hit.name,
                    title=hit.name,
                    url_ref=f"/media/people/{quote(hit.name, safe='')}",
                    snippet=(),
                    score=1.0,
                    facets={
                        "roles": ",".join(hit.roles),
                        "titles": str(hit.titles),
                        **({"portrait": hit.portrait} if hit.portrait else {}),
                    },
                )
                for hit in hits[:limit]
            ],
            next_cursor=encode_cursor(offset + limit) if len(hits) > limit else None,
            facets={"role": counts},
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        return []  # found by name each time


class MediaResolver:
    kind = "media"
    prefixes: tuple[str, ...] = ("media:", "tmdb:", "imdb:", "tvdb:", "isbn:", "igdb:")

    def __init__(self, port: CatalogPort) -> None:
        self.port = port

    async def resolve(self, ref: str, principal: Principal) -> ObjectRef | None:
        found = await self.port.resolve_ref(ref, principal)
        if found is None:
            return None
        return ObjectRef(kind="media", id=str(found.id), title=found.title, route=found.route)


class RequestableSearchProvider:
    """#4: « Ask for it » — the films and series the library does not have, found through the request
    service (Seerr, over TMDB), each opening the page where one asks for it. Titles already available
    are left to the library's own results. #373: the books and games it lacks too, found in the book and
    game databases (Hardcover, IGDB), each opening its sheet — the films and series only for who may ask
    the request service."""

    kind = "request"
    label_key = "search.kind.request"
    required_permission = MEDIA_READ

    def __init__(
        self,
        catalog: Any,
        authorizer: Authorizer,
        language: Any,
        titles: Any = None,
        member_language: Any = None,
    ) -> None:
        self.catalog = catalog
        self.authorizer = authorizer
        self.language = language
        self.titles = titles  # #373: the book and game databases' titles (DatabaseTitles)
        self.member_language = member_language  # #373: the language a member reads titles in

    def facets(self) -> Sequence[FacetDef]:
        # #92: the media subtypes — a book or a game chosen leaves nothing to ask for here
        return (FacetDef("subtype", "search.facet.subtype"),)

    async def _found(
        self, query: ParsedQuery, principal: Principal, limit: int, language: str | None = None
    ) -> list[SearchItem]:
        user = principal.acting_for or principal.user_id
        if user is None or not query.text.strip():
            return []
        if not language:  # the suggestions as one types: the member's own language, as on their pages
            language = await (self.member_language(principal) if self.member_language else self.language())
        wanted = set(query.filters.get("subtype") or ())
        found = (
            await self.titles.found(query.text, language, limit)
            if self.titles is not None and await self.authorizer.is_allowed(principal, MEDIA_READ)
            else []
        )
        found = [item for item in found if not wanted or item.facets.get("type") in wanted]
        if not self.catalog.configured() or not await self.authorizer.is_allowed(principal, MEDIA_REQUEST):
            return found[:limit]
        cards = await self.catalog.search(query.text, user, language)
        items = []
        for card in cards:
            if card["status"] == "available" or (wanted and card["kind"] not in wanted):
                continue
            state = "requested" if card["request"] or card["status"] in ("pending", "processing") else None
            facets = {"type": card["kind"], **({"status": state} if state else {})}
            if card.get("poster"):
                facets["poster"] = str(card["poster"])
            if card.get("year"):
                facets["year"] = str(card["year"])
            items.append(
                SearchItem(
                    kind=self.kind,
                    id=f"{card['kind']}:{card['tmdb_id']}",
                    title=f"{card['title']} ({card['year']})" if card.get("year") else card["title"],
                    url_ref=card["route"],
                    snippet=snippet(str(card.get("overview") or ""), query.terms),
                    score=0.5,
                    facets=facets,
                )
            )
        return interleave(items, found)[:limit]

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        if cursor:  # one page: the request service's first answers are the relevant ones
            return ProviderResult()
        items = await self._found(query, principal, limit, ctx.language if ctx else None)
        return ProviderResult(items=items, took_ms=int((time.perf_counter() - started) * 1000))

    async def suggestions(
        self, query: ParsedQuery, principal: Principal, *, per_type: int = 2
    ) -> Sequence[SearchItem]:
        return (await self._found(query, principal, 6))[:6]

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        return []  # live results only: nothing to bring back later
