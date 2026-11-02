"""News API (contracts/content-contracts.md): reading (list, featured, categories, article) and the
editorial back office (drafts, publish/schedule, feature, archive/restore, delete, translations,
categories). Sensitive actions are audited; deleting an archived article needs a confirmation."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from portalab.capabilities.config import switched_on
from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.capabilities.content.audience import Audience
from portalab.core.audit_port import AuditRecord
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, Forbidden, NotFound, Unavailable
from portalab.modules.news.articles import ArticleInput, ArticleNotFound
from portalab.modules.news.editions.template import Chart, Content
from portalab.modules.news.models import Article, Category
from portalab.modules.news.module import NewsModule
from portalab.modules.news.permissions import (
    NEWS_ARCHIVE,
    NEWS_CATEGORIES,
    NEWS_CREATE,
    NEWS_DELETE,
    NEWS_PUBLISH,
    NEWS_READ,
)
from portalab.modules.news.settings import NEWSLETTER_ON

router = APIRouter(prefix="/api/v1", tags=["news"])


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


def news_module(request: Request) -> NewsModule:
    module = getattr(request.app.state, "news_module", None)
    if not isinstance(module, NewsModule):
        raise Unavailable("News is not available.", code="news.unavailable")
    return module


Module = Annotated[NewsModule, Depends(news_module)]


async def newsletters_on(request: Request) -> None:
    """Issue 246: the newsletters switched off answer nothing (as an address that does not exist)."""
    if not await switched_on(request.app.state.capabilities, NEWSLETTER_ON):
        raise NotFound("The newsletters are switched off.", code="news.newsletters_off")


NewslettersOn = [Depends(newsletters_on)]
Reader = Annotated[Principal, require(NEWS_READ)]
Author = Annotated[Principal, require(NEWS_CREATE)]
Publisher = Annotated[Principal, require(NEWS_PUBLISH)]
Archiver = Annotated[Principal, require(NEWS_ARCHIVE)]
CategoryManager = Annotated[Principal, require(NEWS_CATEGORIES)]


class NewsCard(BaseModel):
    id: UUID
    slug: str
    title: str
    summary: str
    category_id: UUID | None
    published_at: datetime | None
    status: str
    unread: bool = False  # #48: published and not opened yet by this member


class NewsArticleOut(NewsCard):
    html: str
    language: str
    source_language: str
    is_translation: bool
    translation_missing: bool
    archived: bool
    edition_id: UUID | None = None  # #335: the newsletter letter it shows, in place of its body


class NewsEditorOut(NewsCard):
    body_md: str
    audience: dict[str, Any]
    publish_at: datetime | None
    featured_from: datetime | None
    featured_until: datetime | None
    feature_priority: int
    notify_on_publish: bool
    email_on_publish: bool = False  # 027
    emailed_at: datetime | None = None
    version: int
    publish_seq: int
    reads: int = 0  # #48: members who opened it


class NewsReaderOut(BaseModel):
    user_id: UUID
    name: str | None
    read_at: datetime | None = None


class NewsReadersOut(BaseModel):
    read: list[NewsReaderOut]
    unread: list[NewsReaderOut]
    members: int


class NewsListOut(BaseModel):
    items: list[NewsCard]
    next_cursor: str | None


class NewsArticleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=600)
    body_md: str = Field(default="", max_length=500_000)
    category_id: UUID | None = None
    audience: Audience | None = None
    notify_on_publish: bool = False
    email_on_publish: bool = False  # 027: e-mailed to the channel's subscribers when published
    language: str = Field(default="en", max_length=16)
    base_version: int | None = Field(default=None, ge=1)


class NewsScheduleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publish_at: datetime


class NewsFeatureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    featured_from: datetime | None = None
    featured_until: datetime | None = None
    priority: int = Field(default=0, ge=-100, le=100)


class NewsDeleteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: str | None = None


class NewsTranslationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=600)
    body_md: str = Field(max_length=500_000)


class NewsCategoryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,59}$")
    name: str = Field(min_length=1, max_length=120)
    position: int = Field(default=0, ge=0, le=1000)
    enabled: bool = True
    description: str = Field(default="", max_length=300)  # 027: channels
    icon: str | None = Field(default=None, max_length=40)
    newsletter: bool = False


class NewsCategoryOut(BaseModel):
    id: UUID
    key: str
    name: str
    position: int
    enabled: bool
    description: str = ""
    icon: str | None = None
    newsletter: bool = False


def _category_out(c: Category) -> NewsCategoryOut:
    return NewsCategoryOut(
        id=c.id,
        key=c.key,
        name=c.name,
        position=c.position,
        enabled=c.enabled,
        description=c.description,
        icon=c.icon,
        newsletter=c.newsletter,
    )


class NewsletterScheduleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    category_id: UUID
    kind: Literal["releases", "additions", "upcoming", "edition"] = "edition"  # #325: an edition by default
    media_kinds: list[Literal["movie", "series", "book", "game", "album"]] = Field(default_factory=list)
    cadence: Literal["daily", "weekly", "monthly"]
    weekday: int = Field(default=0, ge=0, le=6)
    hour: int = Field(default=9, ge=0, le=23)
    language: str = Field(default="fr", max_length=16)
    email: bool = True
    publish: bool = True  # #332: published in the portal's news (with ``email``: either, or both)
    enabled: bool = True
    template_key: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{1,62}$")  # #316: editions
    notice: str | None = Field(default=None, max_length=2000)
    contents: list[Content] | None = Field(default=None, max_length=14)  # #323: what its editions tell
    charts: list[Chart] | None = Field(default=None, max_length=6)  # #324: its statistics' charts
    subject: str | None = Field(default=None, max_length=200)  # #325: its e-mail's subject, with variables
    days: int | None = Field(default=None, ge=1, le=90)  # #325: the days it tells (else its cadence's)


class NewsletterScheduleOut(NewsletterScheduleIn):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    subscribers: int | None = None  # #326: the members it is e-mailed to
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_article_id: UUID | None


class SubscriptionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: dict[str, bool] = Field(max_length=100)


def _schedule_out(row: Any) -> NewsletterScheduleOut:
    return NewsletterScheduleOut(
        id=row.id,
        name=row.name,
        category_id=row.category_id,
        kind=row.kind,
        media_kinds=row.media_kinds or [],
        cadence=row.cadence,
        weekday=row.weekday,
        hour=row.hour,
        language=row.language,
        email=row.email,
        publish=row.publish,
        enabled=row.enabled,
        template_key=row.template_key,
        notice=row.notice,
        contents=row.contents,
        charts=row.charts,
        subject=row.subject,
        days=row.days,
        last_run_at=row.last_run_at,
        next_run_at=row.next_run_at,
        last_article_id=row.last_article_id,
    )


def _card(row: Article) -> NewsCard:
    return NewsCard(
        id=row.id,
        slug=row.slug,
        title=row.title,
        summary=row.summary,
        category_id=row.category_id,
        published_at=row.published_at,
        status=row.status,
    )


def _editor(row: Article) -> NewsEditorOut:
    return NewsEditorOut(
        **_card(row).model_dump(),
        body_md=row.body_md,
        audience=row.audience,
        publish_at=row.publish_at,
        featured_from=row.featured_from,
        featured_until=row.featured_until,
        feature_priority=row.feature_priority,
        notify_on_publish=row.notify_on_publish,
        email_on_publish=row.email_on_publish,
        emailed_at=row.emailed_at,
        version=row.version,
        publish_seq=row.publish_seq,
    )


def _input(body: NewsArticleIn) -> ArticleInput:
    return ArticleInput(
        title=body.title,
        body_md=body.body_md,
        summary=body.summary,
        category_id=body.category_id,
        audience=body.audience.model_dump() if body.audience else None,
        notify_on_publish=body.notify_on_publish,
        email_on_publish=body.email_on_publish,
        language=body.language,
    )


async def _audit(
    module: NewsModule, principal: Principal, action: str, article: UUID, context: dict[str, Any]
) -> None:
    async with module.database.unit_of_work() as uow:
        await module.audit.record(
            uow.session,
            AuditRecord(
                action=action,
                actor=principal,
                resource=ResourceRef("news_article", str(article)),
                decision="allow",
                result="success",
                context=context,
                sensitive=True,
            ),
        )


# --- reading ---------------------------------------------------------------------------------------------
@router.get("/news", response_model=NewsListOut)
async def list_news(
    principal: Reader,
    module: Module,
    category: Annotated[str | None, Query(max_length=60)] = None,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
) -> NewsListOut:
    rows, next_cursor = await module.articles.listing(principal, category=category, cursor=cursor)
    return NewsListOut(items=await _cards(module, principal, rows), next_cursor=next_cursor)


async def _cards(module: NewsModule, principal: Principal, rows: list[Any]) -> list[NewsCard]:
    """#48: the cards, each saying whether this member has opened it yet."""
    read = await module.articles.read_ids(principal.user_id, [r.id for r in rows])
    cards = [_card(r) for r in rows]
    for card in cards:
        card.unread = card.status == "published" and card.id not in read and principal.user_id is not None
    return cards


@router.get("/news/featured", response_model=list[NewsCard])
async def featured(principal: Reader, module: Module) -> list[NewsCard]:
    return await _cards(module, principal, await module.articles.featured(principal))


@router.get("/news/categories", response_model=list[NewsCategoryOut])
async def categories(principal: Reader, module: Module) -> list[NewsCategoryOut]:
    return [
        NewsCategoryOut(id=c.id, key=c.key, name=c.name, position=c.position, enabled=c.enabled)
        for c in await module.articles.categories()
    ]


@router.get("/news/{slug}", response_model=NewsArticleOut)
async def article(
    principal: Reader, slug: str, module: Module, lang: Annotated[str | None, Query(max_length=16)] = None
) -> NewsArticleOut:
    row = await module.articles.get(slug, principal)
    translation = await module.articles.translation(row, lang)
    card = _card(row)
    if translation is not None:
        card.title, card.summary = translation.title, translation.summary
    return NewsArticleOut(
        **card.model_dump(),
        html=translation.rendered_html if translation else row.rendered_html,
        language=translation.language if translation else row.language,
        source_language=row.language,
        is_translation=translation is not None,
        translation_missing=bool(lang and lang != row.language and translation is None),
        archived=row.status == "archived",
        edition_id=row.edition_id,
    )


@router.post("/news/{slug}/read", status_code=status.HTTP_204_NO_CONTENT)
async def read(principal: Reader, slug: str, module: Module) -> Response:
    """#48: the member opened the article (remembered once)."""
    await module.articles.mark_read(principal, slug)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- editorial -------------------------------------------------------------------------------------------
@router.get("/admin/news/articles", response_model=list[NewsEditorOut])
async def editorial(
    principal: Author,
    module: Module,
    status_filter: Annotated[str | None, Query(alias="status", max_length=12)] = None,
) -> list[NewsEditorOut]:
    rows = await module.articles.editorial(principal, status_filter)
    counts = await module.articles.read_counts([r.id for r in rows])
    out = [_editor(r) for r in rows]
    for item in out:
        item.reads = counts.get(item.id, 0)
    return out


@router.get("/admin/news/articles/{article_id}/readers", response_model=NewsReadersOut)
async def readers(principal: Author, article_id: UUID, module: Module) -> NewsReadersOut:
    """#48: who opened the article, and the members who have not yet."""
    return NewsReadersOut.model_validate(await module.articles.readers(principal, article_id))


@router.get("/admin/news/articles/{article_id}", response_model=NewsEditorOut)
async def editorial_one(principal: Author, article_id: UUID, module: Module) -> NewsEditorOut:
    row = await module.articles.by_key(str(article_id))
    if row is None or row.status == "deleted" or not await module.articles.readable(row, principal):
        raise ArticleNotFound("This article does not exist.")
    return _editor(row)


@router.post("/admin/news/articles", response_model=NewsEditorOut, status_code=status.HTTP_201_CREATED)
async def create(principal: Author, body: NewsArticleIn, module: Module) -> NewsEditorOut:
    return _editor(await module.articles.create(principal, _input(body)))


@router.patch("/admin/news/articles/{article_id}", response_model=NewsEditorOut)
async def update(principal: Author, article_id: UUID, body: NewsArticleIn, module: Module) -> NewsEditorOut:
    return _editor(await module.articles.update(principal, article_id, _input(body), body.base_version))


@router.post("/admin/news/articles/{article_id}/schedule", response_model=NewsEditorOut)
async def schedule(
    principal: Publisher, article_id: UUID, body: NewsScheduleIn, module: Module
) -> NewsEditorOut:
    row = await module.articles.transition(principal, article_id, "schedule", publish_at=body.publish_at)
    await _audit(module, principal, "news.schedule", article_id, {"publish_at": body.publish_at.isoformat()})
    return _editor(row)


@router.post("/admin/news/articles/{article_id}/lifecycle/{action}", response_model=NewsEditorOut)
async def lifecycle(
    principal: Archiver, article_id: UUID, action: Literal["archive", "restore"], module: Module
) -> NewsEditorOut:
    row = await module.articles.transition(principal, article_id, action)
    await _audit(module, principal, f"news.{action}", article_id, {})
    return _editor(row)


@router.post("/admin/news/articles/{article_id}/feature", response_model=NewsEditorOut)
async def feature(
    principal: Publisher, article_id: UUID, body: NewsFeatureIn, module: Module
) -> NewsEditorOut:
    row = await module.articles.feature(
        principal, article_id, body.featured_from, body.featured_until, body.priority
    )
    return _editor(row)


@router.post("/admin/news/articles/{article_id}/unfeature", response_model=NewsEditorOut)
async def unfeature(principal: Publisher, article_id: UUID, module: Module) -> NewsEditorOut:
    return _editor(await module.articles.unfeature(principal, article_id))


@router.post("/admin/news/articles/{article_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete(principal: Author, article_id: UUID, body: NewsDeleteIn, module: Module) -> Response:
    row = await module.articles.by_key(str(article_id))
    if row is not None and row.status == "archived":  # irreversible on published history: confirm
        providers = module.capabilities.system_providers(CONFIRMATIONS)
        if not providers:
            raise Unavailable("Confirmations are not available.", code="authz.unavailable")
        confirmations = providers[0].provider
        resource, payload = ResourceRef("news_article", str(article_id)), {"delete": str(article_id)}
        if body.confirmation is None:
            issued = await confirmations.issue(principal, NEWS_DELETE, resource, payload)
            raise ConfirmationRequired(
                "Deleting a published article cannot be undone.", extensions={"confirmation": issued}
            )
        if not await confirmations.consume(body.confirmation, principal, NEWS_DELETE, resource, payload):
            raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")
    await module.articles.delete(principal, article_id)
    await _audit(module, principal, "news.delete", article_id, {})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/admin/news/articles/{article_id}/translations/{language}", response_model=NewsEditorOut)
async def translate(
    principal: Author, article_id: UUID, language: str, body: NewsTranslationIn, module: Module
) -> NewsEditorOut:
    return _editor(
        await module.articles.translate(
            principal, article_id, language[:16], body.title, body.summary, body.body_md
        )
    )


@router.get("/admin/news/categories", response_model=list[NewsCategoryOut])
async def all_categories(principal: CategoryManager, module: Module) -> list[NewsCategoryOut]:
    return [_category_out(c) for c in await module.articles.categories(enabled_only=False)]


@router.put("/admin/news/categories", response_model=NewsCategoryOut)
async def put_category(principal: CategoryManager, body: NewsCategoryIn, module: Module) -> NewsCategoryOut:
    async with module.database.unit_of_work() as uow:
        row = (
            await uow.session.execute(select(Category).where(Category.key == body.key))
        ).scalar_one_or_none()
        if row is None:
            row = Category(key=body.key, name=body.name, position=body.position, enabled=body.enabled)
            uow.session.add(row)
        else:
            row.name, row.position, row.enabled = body.name, body.position, body.enabled
        row.description, row.icon, row.newsletter = body.description, body.icon, body.newsletter
        await uow.session.flush()
        out = _category_out(row)
    return out


# --- newsletters (027) -----------------------------------------------------------------------------------
@router.get("/me/newsletters")
async def my_newsletters(principal: Reader, module: Module, request: Request) -> list[dict[str, Any]]:
    """The automatic newsletters (#326) and the channels sent by e-mail, and whether I receive each one."""
    user = principal.acting_for or principal.user_id
    if not await switched_on(request.app.state.capabilities, NEWSLETTER_ON):
        return []
    return await module.newsletters.subscriptions(user) if user else []


@router.put("/me/newsletters", dependencies=NewslettersOn)
async def set_my_newsletters(
    principal: Reader, body: SubscriptionsIn, module: Module
) -> list[dict[str, Any]]:
    await module.newsletters.set_subscriptions(principal, body.changes)
    user = principal.acting_for or principal.user_id
    return await module.newsletters.subscriptions(user) if user else []


@router.get("/admin/news/newsletters", response_model=list[NewsletterScheduleOut], dependencies=NewslettersOn)
async def schedules(principal: Publisher, module: Module) -> list[NewsletterScheduleOut]:
    out = []
    for row in await module.newsletters.schedules():
        item = _schedule_out(row)
        if row.kind == "edition" and row.email:  # #326: how many members receive it
            item.subscribers = await module.newsletters.subscribers(row)
        out.append(item)
    return out


@router.post(
    "/admin/news/newsletters",
    response_model=NewsletterScheduleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=NewslettersOn,
)
async def create_schedule(
    principal: Publisher, body: NewsletterScheduleIn, module: Module
) -> NewsletterScheduleOut:
    return _schedule_out(await module.newsletters.save_schedule(None, body.model_dump()))


@router.put(
    "/admin/news/newsletters/{schedule_id}", response_model=NewsletterScheduleOut, dependencies=NewslettersOn
)
async def update_schedule(
    principal: Publisher, schedule_id: UUID, body: NewsletterScheduleIn, module: Module
) -> NewsletterScheduleOut:
    return _schedule_out(await module.newsletters.save_schedule(schedule_id, body.model_dump()))


@router.delete(
    "/admin/news/newsletters/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=NewslettersOn,
)
async def delete_schedule(principal: Publisher, schedule_id: UUID, module: Module) -> Response:
    await module.newsletters.delete_schedule(schedule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/admin/news/newsletters/{schedule_id}/run", dependencies=NewslettersOn)
async def run_schedule(principal: Publisher, schedule_id: UUID, module: Module) -> dict[str, Any]:
    """Write the newsletter now (« preview » it in the news desk); nothing when there is nothing to tell."""
    written = await module.newsletters.generate(schedule_id, force=True)
    if isinstance(written, Article):
        return {"article": _editor(written).model_dump(mode="json"), "edition": None}
    # #316: an « edition » schedule writes an edition
    return {"article": None, "edition": str(written.id) if written is not None else None}


@router.post("/admin/news/newsletters/{schedule_id}/test", dependencies=NewslettersOn)
async def test_schedule(
    principal: Publisher, schedule_id: UUID, module: Module, request: Request
) -> dict[str, Any]:
    """#334: the letter e-mailed to me alone — and published in the news when the newsletter goes there."""
    if principal.user_id is None:
        raise NotFound("No account.", code="news.no_account")
    base = str(request.base_url).rstrip("/")
    edition, article, sent = await module.newsletters.try_out(schedule_id, principal.user_id, base)
    return {
        "sent": sent,
        "edition": str(edition.id),
        "article": str(article.id) if article is not None else None,
    }


@router.post("/admin/news/articles/{article_id}/{action}", response_model=NewsEditorOut)
async def publication(
    principal: Publisher,
    article_id: UUID,
    action: Literal["publish", "unschedule"],
    module: Module,
) -> NewsEditorOut:
    row = await module.articles.transition(principal, article_id, action)
    await _audit(module, principal, f"news.{action}", article_id, {"publish_seq": row.publish_seq})
    return _editor(row)
