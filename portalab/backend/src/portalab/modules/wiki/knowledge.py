"""Knowledge surfaces (T016; R10): ``support.knowledge`` for Support's precheck/diagnosis and AI (only
pages the **asking principal** may read; ``for_ai`` additionally requires ``readable_by_ai``), the
``content.help`` resolver for the contextual help slot, the ``wiki`` search provider (008) and the
``wiki`` link resolver (per-viewer states, no title for forbidden pages)."""

import time
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import cast, func, literal, or_, select
from sqlalchemy.dialects.postgresql import JSONB, REGCONFIG

from portalab.capabilities.content import ContentRef, KnowledgeHit, ResolvedLink
from portalab.capabilities.i18n import LocaleContext, normalize_for_search
from portalab.capabilities.search import FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.capabilities.search.fts import decode_cursor, encode_cursor, snippet
from portalab.core.authz_port import Principal
from portalab.modules.wiki.models import Page, PageTag, Revision
from portalab.modules.wiki.pages import PageService
from portalab.modules.wiki.permissions import WIKI_READ


def _query(text: str) -> Any:
    return func.websearch_to_tsquery(cast(literal("simple"), REGCONFIG), normalize_for_search(text)[:500])


class WikiKnowledge:
    def __init__(self, pages: PageService) -> None:
        self.pages = pages

    async def _hits(
        self, rows: Sequence[Any], principal: Principal, limit: int, for_ai: bool
    ) -> list[KnowledgeHit]:
        out: list[KnowledgeHit] = []
        for page, text, rank in rows:
            if for_ai and not page.readable_by_ai:
                continue
            if page.status != "published" or not await self.pages.readable(page, principal):
                continue
            out.append(
                KnowledgeHit(
                    ref=ContentRef("wiki", str(page.id)).format(),
                    title=page.title,
                    excerpt=" ".join(str(text).split())[:300],
                    url=f"/wiki/{page.slug}",
                    score=float(rank or 0.0),
                )
            )
            if len(out) >= limit:
                break
        return out

    async def search(
        self, text: str, principal: Principal, *, limit: int = 5, for_ai: bool = False
    ) -> Sequence[KnowledgeHit]:
        if not text.strip() or not await self.pages.allowed(principal, WIKI_READ):
            return []
        query = _query(text)
        async with self.pages.database.session() as session:
            rows = (
                await session.execute(
                    select(
                        Page, Revision.plain_text, func.ts_rank_cd(Page.search_vector, query).label("rank")
                    )
                    .join(
                        Revision, (Revision.page_id == Page.id) & (Revision.version == Page.current_version)
                    )
                    .where(Page.search_vector.op("@@")(query), Page.status == "published")
                    .order_by(func.ts_rank_cd(Page.search_vector, query).desc(), Page.title)
                    .limit(limit * 5)
                )
            ).all()
        return await self._hits(rows, principal, limit, for_ai)

    async def for_context(self, key: str, principal: Principal) -> Sequence[KnowledgeHit]:
        if not key.strip():
            return []
        async with self.pages.database.session() as session:
            rows = (
                await session.execute(
                    select(Page, Revision.plain_text, literal(1.0))
                    .join(
                        Revision, (Revision.page_id == Page.id) & (Revision.version == Page.current_version)
                    )
                    .where(Page.help_keys.op("@>")(cast([key.strip()], JSONB)), Page.status == "published")
                    .order_by(Page.position, Page.title)
                    .limit(20)
                )
            ).all()
        return await self._hits(rows, principal, 5, False)


class WikiSearchProvider:
    kind = "wiki"
    label_key = "search.kind.wiki"
    required_permission = WIKI_READ

    def __init__(self, pages: PageService) -> None:
        self.pages = pages

    def facets(self) -> Sequence[FacetDef]:
        return (FacetDef("tag", "search.facet.tag", kind="text"),)

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        if not query.text.strip() or not await self.pages.allowed(principal, WIKI_READ):
            return ProviderResult()
        tsquery = _query(query.text)
        stmt = (
            select(Page, Revision.plain_text)
            .join(Revision, (Revision.page_id == Page.id) & (Revision.version == Page.current_version))
            .where(Page.status.in_(("published", "archived")))
            .where(
                or_(Page.search_vector.op("@@")(tsquery), Page.title.ilike(f"%{query.text.strip()[:80]}%"))
            )
            .order_by(func.ts_rank_cd(Page.search_vector, tsquery).desc(), Page.title)
        )
        if query.filters.get("tag"):
            stmt = stmt.where(
                Page.id.in_(select(PageTag.page_id).where(PageTag.tag.in_(list(query.filters["tag"]))))
            )
        async with self.pages.database.session() as session:
            rows = (await session.execute(stmt.limit(500))).all()
        visible = [(p, t) for p, t in rows if await self.pages.readable(p, principal)]
        offset = decode_cursor(cursor)
        page_rows = visible[offset : offset + limit]
        return ProviderResult(
            items=[self._item(p, t, query) for p, t in page_rows],
            next_cursor=encode_cursor(offset + limit) if offset + limit < len(visible) else None,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    def _item(self, page: Page, text: str, query: ParsedQuery) -> SearchItem:
        return SearchItem(
            kind=self.kind,
            id=str(page.id),
            title=page.title,
            url_ref=f"/wiki/{page.slug}",
            snippet=snippet(text or page.title, query.terms),
            facets={"status": page.status},
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        out: list[SearchItem] = []
        empty = ParsedQuery(text="", normalized="", terms=())
        async with self.pages.database.session() as session:
            for value in ids:
                try:
                    page = await session.get(Page, UUID(value))
                except ValueError:
                    continue
                if page is not None and page.status != "draft" and await self.pages.readable(page, principal):
                    out.append(self._item(page, "", empty))
        return out


class WikiLinkResolver:
    kind = "wiki"

    def __init__(self, pages: PageService) -> None:
        self.pages = pages

    async def resolve(self, refs: Sequence[ContentRef], viewer: Principal) -> dict[str, ResolvedLink]:
        out: dict[str, ResolvedLink] = {}
        async with self.pages.database.session() as session:
            for ref in refs:
                key = ref.format()
                page = None
                try:
                    page = await session.get(Page, UUID(ref.id))
                except ValueError:
                    page = (
                        await session.execute(select(Page).where(Page.slug == ref.id))
                    ).scalar_one_or_none()
                if page is None or page.status == "deleted":
                    out[key] = ResolvedLink(key, "deleted" if page is not None else "unavailable")
                elif not await self.pages.readable(page, viewer):
                    out[key] = ResolvedLink(key, "forbidden")
                elif page.status == "archived":
                    out[key] = ResolvedLink(key, "archived", page.title, f"/wiki/{page.slug}")
                else:
                    out[key] = ResolvedLink(key, "ok", page.title, f"/wiki/{page.slug}")
        return out
