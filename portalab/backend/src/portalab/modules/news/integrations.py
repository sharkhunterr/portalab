"""News integrations (T019, T022, T025, T034): the ``news`` search provider (008), widgets
``news.featured|latest`` (009), the ``news`` link resolver, the ``news`` calendar source (publications;
scheduled ones for editors only) and the 019 action ``content.publish`` (runs as the author's principal)."""

import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import UUID

from portalab.capabilities.automation_actions import ActionRegistry, ActionType
from portalab.capabilities.content import CalendarItem, CalendarSourceResult, ContentRef, ResolvedLink
from portalab.capabilities.dashboard import (
    Refresh,
    Size,
    SizeLimits,
    WidgetDefinition,
    WidgetPayload,
    with_styles,
)
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search import FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.capabilities.search.fts import snippet
from portalab.core.authz_port import Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.news.articles import ArticleService
from portalab.modules.news.models import Article
from portalab.modules.news.permissions import NEWS_PUBLISH, NEWS_READ

OWNER = "module:news"


class NewsSearchProvider:
    kind = "news"
    label_key = "search.kind.news"
    required_permission = NEWS_READ

    def __init__(self, articles: ArticleService) -> None:
        self.articles = articles

    def facets(self) -> Sequence[FacetDef]:
        return ()

    def _item(self, row: Article, query: ParsedQuery) -> SearchItem:
        return SearchItem(
            kind=self.kind,
            id=str(row.id),
            title=row.title,
            url_ref=f"/news/{row.slug}",
            snippet=snippet(row.summary or row.plain_text[:400], query.terms),
        )

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        if not query.text.strip() or not await self.articles.allowed(principal, NEWS_READ):
            return ProviderResult()
        rows, next_cursor = await self.articles.listing(principal, q=query.text, cursor=cursor)
        return ProviderResult(
            items=[self._item(r, query) for r in rows[:limit]],
            next_cursor=next_cursor,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        empty = ParsedQuery(text="", normalized="", terms=())
        out = []
        for value in ids:
            row = await self.articles.by_key(value)
            if row is not None and row.status == "published" and await self.articles.readable(row, principal):
                out.append(self._item(row, empty))
        return out


class NewsLinkResolver:
    kind = "news"

    def __init__(self, articles: ArticleService) -> None:
        self.articles = articles

    async def resolve(self, refs: Sequence[ContentRef], viewer: Principal) -> dict[str, ResolvedLink]:
        out: dict[str, ResolvedLink] = {}
        for ref in refs:
            key = ref.format()
            row = await self.articles.by_key(ref.id)
            if row is None:
                out[key] = ResolvedLink(key, "unavailable")
            elif row.status == "deleted":
                out[key] = ResolvedLink(key, "deleted")
            elif not await self.articles.readable(row, viewer):
                out[key] = ResolvedLink(key, "forbidden")
            else:
                state = "archived" if row.status == "archived" else "ok"
                out[key] = ResolvedLink(key, state, row.title, f"/news/{row.slug}")  # type: ignore[arg-type]
        return out


class NewsCalendarSource:
    kind = "news"
    label_key = "calendar:source.news"

    def __init__(self, articles: ArticleService) -> None:
        self.articles = articles

    def _item(self, row: Article) -> CalendarItem:
        at = row.published_at if row.status == "published" else row.publish_at
        return CalendarItem(
            source_kind=self.kind,
            source_id=str(row.id),
            type="publication",
            title=row.title,
            starts_at=at,
            status=row.status,
            url_ref=f"/news/{row.slug}",
        )

    async def items(
        self, start: datetime, end: datetime, viewer: Principal, ctx: LocaleContext
    ) -> CalendarSourceResult:
        rows = await self.articles.in_range(start, end, viewer)
        return CalendarSourceResult(items=[self._item(r) for r in rows], as_of=utc_now(self.articles.clock))

    async def item(self, source_id: str, viewer: Principal) -> CalendarItem | None:
        row = await self.articles.by_key(source_id)
        if (
            row is None
            or row.status not in ("published", "scheduled")
            or not await self.articles.readable(row, viewer)
        ):
            return None
        return self._item(row)


def _widget(key: str, title: str) -> WidgetDefinition:
    return WidgetDefinition(
        key=key,
        owner=OWNER,
        title_key=f"news:widget.{title}.title",
        description_key=f"news:widget.{title}.description",
        icon="newspaper",
        required_permission=NEWS_READ,
        size=SizeLimits(default=Size(6, 3), min=Size(3, 1), max=Size(12, 6)),
        refresh=Refresh(
            mode="event", events=("news.article_published", "news.article_featured", "news.article_archived")
        ),
        stale_after_s=900,
        template="list",
    )


FEATURED = _widget("news.featured", "featured")
LATEST = with_styles(  # 027 (#31): the list, or « carousel » — one article at a time, then the next
    replace(
        _widget("news.latest", "latest"),
        component_id="news.latest",
        size=SizeLimits(default=Size(6, 3), min=Size(3, 1), max=Size(12, 6)),  # one row: the latest headline
    ),
    "carousel",
)


class NewsWidget:
    def __init__(self, articles: ArticleService, featured: bool, clock: Clock | None = None) -> None:
        self.articles = articles
        self.is_featured = featured
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        rows = (
            await self.articles.featured(principal)
            if self.is_featured
            else (await self.articles.listing(principal))[0][:5]
        )
        if not rows:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        items = [
            {
                "title": r.title,
                "route": f"/news/{r.slug}",
                "meta": r.published_at.date().isoformat() if r.published_at else "",
                "summary": r.summary,
                "cover": str(r.category_id or r.slug),  # 027: the seed of its generated cover
            }
            for r in rows
        ]
        return WidgetPayload("available", as_of=utc_now(self.clock), data={"items": items})


def register_publish_action(articles: ArticleService, registry: ActionRegistry) -> None:
    async def run(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        row = await articles.transition(principal, UUID(str(params["article"])), "publish")
        return {"article": str(row.id), "publish_seq": row.publish_seq}

    if registry.get("content.publish") is None:
        registry.register(
            ActionType(
                key="content.publish",
                description="Publish a news article (as the automation's author)",
                permission=NEWS_PUBLISH,
                idempotency="state guard: a published article is never published twice",
                run=run,
                owner=OWNER,
                params_schema={"article": "uuid"},
            )
        )
