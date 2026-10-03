"""Search integration (T028; 008 SDK): ``SearchProvider(kind="media")`` with ``type``, ``genre``, ``year``
and ``availability`` facets, scoped by ``media.read`` at the source, plus the ``media:`` / ``tmdb:``…
``ObjectResolver`` and the palette actions ``media.open`` / ``media.request``."""

import time
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, select

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
from portalab.modules.media.models import MediaObject, ObjectTag
from portalab.modules.media.permissions import MEDIA_READ, MEDIA_REQUEST

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

    def _item(self, row: MediaObject, query: ParsedQuery, score: float = 0.0) -> SearchItem:
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
                (await session.execute(stmt.order_by(MediaObject.sort_title).offset(offset).limit(limit + 1)))
                .scalars()
                .all()
            )
        facets: dict[str, dict[str, int]] = {"type": {}, "availability": {}}
        for row in rows[:limit]:
            facets["type"][row.kind] = facets["type"].get(row.kind, 0) + 1
            state = "available" if row.available else "unavailable"
            facets["availability"][state] = facets["availability"].get(state, 0) + 1
        return ProviderResult(
            items=[self._item(row, query, 1.0) for row in rows[:limit]],
            next_cursor=encode_cursor(offset + limit) if len(rows) > limit else None,
            facets=facets,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

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
        return [self._item(row, empty) for row in rows]


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
