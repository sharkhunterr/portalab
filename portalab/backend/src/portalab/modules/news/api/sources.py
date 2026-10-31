"""HTTP API of the news sources (#299): the editors add RSS/Atom sources (previewed before saving), read
them now, pin or hide an item; readers see the latest items, a source's, or those naming a library title or a
person — each with its copied picture, never the site's own."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status
from pydantic import BaseModel, Field

from portalab.core.errors import NotFound, ValidationFailed
from portalab.modules.news.api.router import CategoryManager, Module, Reader
from portalab.modules.news.models import Feed, FeedItem
from portalab.modules.news.sources.service import SourceRefused

router = APIRouter(prefix="/api/v1", tags=["news"])


class NewsSourceIn(BaseModel):
    id: UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=8, max_length=1000, pattern=r"^https?://")
    category_id: UUID | None = None
    enabled: bool = True
    include_words: list[str] = Field(default=[], max_length=30)
    exclude_words: list[str] = Field(default=[], max_length=30)
    refresh_minutes: int = Field(default=60, ge=15, le=1440)


class NewsSourceOut(BaseModel):
    id: UUID
    name: str
    url: str
    site_url: str | None
    category_id: UUID | None
    enabled: bool
    include_words: list[str]
    exclude_words: list[str]
    refresh_minutes: int
    status: str  # never | ok | error
    last_error: str | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    items: int = 0


class NewsSourcesOut(BaseModel):
    items: list[NewsSourceOut]


class SourceMention(BaseModel):
    kind: str  # title | person
    ref: str
    label: str
    route: str


class SourceItemOut(BaseModel):
    id: UUID
    source_id: UUID
    source: str
    category_id: UUID | None
    title: str
    summary: str
    link: str
    picture: str | None  # the portal's copy (``/api/v1/news/sources/items/{id}/picture``)
    published_at: datetime
    mentions: list[SourceMention]
    pinned: bool
    hidden: bool


class SourceItemsOut(BaseModel):
    items: list[SourceItemOut]


class SourcePreviewIn(BaseModel):
    url: str = Field(min_length=8, max_length=1000, pattern=r"^https?://")


class SourcePreviewItemOut(BaseModel):
    title: str
    summary: str
    link: str
    published_at: datetime | None
    mentions: list[SourceMention]


class SourcePreviewOut(BaseModel):
    url: str
    title: str
    site: str | None
    items: list[SourcePreviewItemOut]


class SourceRefreshOut(BaseModel):
    added: int
    status: str
    last_error: str | None


class SourceItemMarkIn(BaseModel):
    pinned: bool | None = None
    hidden: bool | None = None


def _source(feed: Feed, count: int = 0) -> NewsSourceOut:
    return NewsSourceOut(
        id=feed.id,
        name=feed.name,
        url=feed.url,
        site_url=feed.site_url,
        category_id=feed.category_id,
        enabled=feed.enabled,
        include_words=list(feed.include_words or []),
        exclude_words=list(feed.exclude_words or []),
        refresh_minutes=feed.refresh_minutes,
        status=feed.status,
        last_error=feed.last_error,
        last_run_at=feed.last_run_at,
        next_run_at=feed.next_run_at,
        items=count,
    )


def _item(item: FeedItem, feed: Feed) -> SourceItemOut:
    return SourceItemOut(
        id=item.id,
        source_id=feed.id,
        source=feed.name,
        category_id=feed.category_id,
        title=item.title,
        summary=item.summary,
        link=item.link,
        picture=f"/api/v1/news/sources/items/{item.id}/picture" if item.image_key else None,
        published_at=item.published_at,
        mentions=[SourceMention.model_validate(m) for m in item.mentions or []],
        pinned=item.pinned,
        hidden=item.hidden,
    )


# --- readers ------------------------------------------------------------------------------------------
@router.get("/news/sources/items", response_model=SourceItemsOut)
async def source_items(
    _: Reader,
    module: Module,
    source: Annotated[list[UUID], Query(max_length=50)] = [],  # noqa: B006 — FastAPI's list query
    title: Annotated[list[str], Query(max_length=100)] = [],  # noqa: B006
    person: Annotated[list[str], Query(max_length=100)] = [],  # noqa: B006
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> SourceItemsOut:
    """The latest news from elsewhere (pinned first), a source's, or those naming library titles (their
    ids) or people (their names as the library credits them)."""
    rows = await module.sources.items(feeds=source, titles=title, people=person, limit=limit)
    return SourceItemsOut(items=[_item(item, feed) for item, feed in rows])


@router.get("/news/sources/items/{item_id}/picture")
async def source_picture(_: Reader, item_id: UUID, module: Module, request: Request) -> Response:
    found = await module.sources.picture(item_id)
    if found is None:
        raise NotFound("No picture for this item.", code="news.picture_not_found")
    key, data = found
    tag = f'"{key.rsplit("/", 1)[-1][:32]}"'
    headers = {"Cache-Control": "private, max-age=86400", "ETag": tag, "X-Content-Type-Options": "nosniff"}
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers=headers)
    kind = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return Response(content=data, media_type=kind, headers=headers)


# --- the editors --------------------------------------------------------------------------------------
@router.get("/admin/news/sources", response_model=NewsSourcesOut)
async def sources(_: CategoryManager, module: Module) -> NewsSourcesOut:
    return NewsSourcesOut(items=[_source(feed, count) for feed, count in await module.sources.sources()])


@router.post("/admin/news/sources/preview", response_model=SourcePreviewOut)
async def preview(_: CategoryManager, module: Module, body: SourcePreviewIn) -> SourcePreviewOut:
    """What a source would bring — read now, nothing kept."""
    try:
        found = await module.sources.preview(body.url)
    except SourceRefused as exc:
        raise ValidationFailed(str(exc), code="news.source_refused") from exc
    items = [
        SourcePreviewItemOut(
            title=item.title,
            summary=item.summary,
            link=item.link,
            published_at=item.published,
            mentions=[SourceMention.model_validate(m) for m in mentions],
        )
        for item, mentions in zip(found.feed.items[:10], found.mentions, strict=False)
    ]
    return SourcePreviewOut(url=found.url, title=found.feed.title, site=found.feed.site, items=items)


@router.put("/admin/news/sources", response_model=NewsSourceOut)
async def save_source(_: CategoryManager, module: Module, body: NewsSourceIn) -> NewsSourceOut:
    """Add a source (read at once) or change one."""
    fields = body.model_dump(exclude={"id"})
    fields["include_words"] = [w.strip() for w in body.include_words if w.strip()]
    fields["exclude_words"] = [w.strip() for w in body.exclude_words if w.strip()]
    try:
        feed_id = await module.sources.save(body.id, fields)
    except SourceRefused as exc:
        raise ValidationFailed(str(exc), code="news.source_refused") from exc
    if body.id is None and body.enabled:
        await module.sources.refresh(feed_id)
    for feed, count in await module.sources.sources():
        if feed.id == feed_id:
            return _source(feed, count)
    raise NotFound("No such source.", code="news.source_not_found")


@router.delete("/admin/news/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_source(_: CategoryManager, module: Module, source_id: UUID) -> None:
    await module.sources.remove(source_id)


@router.post("/admin/news/sources/{source_id}/refresh", response_model=SourceRefreshOut)
async def refresh_source(_: CategoryManager, module: Module, source_id: UUID) -> SourceRefreshOut:
    """Read a source now."""
    added = await module.sources.refresh(source_id)
    for feed, _count in await module.sources.sources():
        if feed.id == source_id:
            return SourceRefreshOut(added=added, status=feed.status, last_error=feed.last_error)
    raise NotFound("No such source.", code="news.source_not_found")


@router.get("/admin/news/sources/items", response_model=SourceItemsOut)
async def admin_items(
    _: CategoryManager,
    module: Module,
    source: Annotated[list[UUID], Query(max_length=50)] = [],  # noqa: B006
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SourceItemsOut:
    """The latest items, the hidden ones too (to bring them back)."""
    rows = await module.sources.items(feeds=source, hidden=True, limit=limit)
    return SourceItemsOut(items=[_item(item, feed) for item, feed in rows])


@router.put("/admin/news/sources/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def mark_item(_: CategoryManager, module: Module, item_id: UUID, body: SourceItemMarkIn) -> None:
    """Pin an item on « À la une », or hide it."""
    if not await module.sources.mark(item_id, pinned=body.pinned, hidden=body.hidden):
        raise NotFound("No such item.", code="news.item_not_found")
