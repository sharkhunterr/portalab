"""Search integration (T028; 008 SDK): ``SearchProvider(kind="media")`` with ``type``, ``genre``, ``year``
and ``availability`` facets, scoped by ``media.read`` at the source, plus the ``media:`` / ``tmdb:``…
``ObjectResolver`` and the palette actions ``media.open`` / ``media.request``."""

import time
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, select

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
from portalab.modules.media.models import MediaObject, MediaRequest, ObjectTag
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
            FacetDef("type", "search.facet.type"),
            FacetDef("genre", "search.facet.genre", kind="text"),
            FacetDef("year", "search.facet.year", kind="text"),
            FacetDef("availability", "search.facet.availability", values=("available", "unavailable")),
        )

    async def _extras(self, rows: Sequence[MediaObject]) -> dict[UUID, dict[str, str]]:
        """#67: what a result shows beside its title — the poster, the first genres and the title's state
        (available, requested — a request in progress — or not available)."""
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
        stmt = select(MediaObject).where(MediaObject.status == "active")
        filters = query.filters
        if filters.get("type"):
            stmt = stmt.where(MediaObject.kind.in_(filters["type"]))
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
        if query.terms:
            stmt = stmt.where(and_(*(MediaObject.sort_title.ilike(f"%{t}%") for t in query.terms[:8])))
        offset = decode_cursor(cursor)
        async with self.query.database.session() as session:
            rows = (
                (
                    await session.execute(
                        stmt.order_by(*self._relevance(query)).offset(offset).limit(limit + 1)
                    )
                )
                .scalars()
                .all()
            )
        facets: dict[str, dict[str, int]] = {"type": {}, "availability": {}}
        for row in rows[:limit]:
            facets["type"][row.kind] = facets["type"].get(row.kind, 0) + 1
            state = "available" if row.available else "unavailable"
            facets["availability"][state] = facets["availability"].get(state, 0) + 1
        extras = await self._extras(rows[:limit])
        return ProviderResult(
            items=[self._item(row, query, 1.0, extras.get(row.id)) for row in rows[:limit]],
            next_cursor=encode_cursor(offset + limit) if len(rows) > limit else None,
            facets=facets,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    @staticmethod
    def _relevance(query: ParsedQuery) -> list[Any]:
        """#67: the most relevant first — the exact title, a title starting with the words, a word of the
        title starting with them, then the rest; then films and series before books…; then A to Z. (Sorting
        A to Z alone put « 095 [An +001] Star Wars… » books before every « Star Wars » film.)"""
        kind_rank = case(
            *((MediaObject.kind == kind, index) for index, kind in enumerate(KIND_ORDER)),
            else_=len(KIND_ORDER),
        )
        text = " ".join(query.terms).strip().lower()
        if not text:
            return [kind_rank, MediaObject.sort_title]
        title = func.lower(MediaObject.title)
        safe = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        tier = case(
            (title == text, 0),
            (title.like(f"{safe}%", escape="\\"), 1),
            (title.like(f"% {safe}%", escape="\\"), 2),
            else_=3,
        )
        return [tier, kind_rank, MediaObject.sort_title]

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
