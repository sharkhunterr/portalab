"""``ArticleService`` (T019, T022; R6, R7): the editorial lifecycle and every read surface.

States: ``draft → published`` or ``draft → scheduled → published`` (job at ``publish_at``; the state check
and ``publish_seq`` make duplicate job runs harmless), ``published → archived → published`` (restore),
``scheduled → draft``; ``deleted`` is a tombstone (links show "deleted"). Readers see published (and,
by direct link, archived) articles within the article's audience; drafts and scheduled articles exist for
editors only. Featuring is a window evaluated at read time, capped by ``news.maxFeatured`` and ordered by
priority then recency."""

import asyncio
import re
import unicodedata
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.content.audience import Audience, can_read
from portalab.capabilities.content.render import RENDERER_VERSION, render_markdown_async
from portalab.capabilities.i18n import normalize_for_search
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.identity_directory import CONTACT
from portalab.capabilities.notifications import (
    NOTIFY,
    AllAuthenticated,
    CommunicationRequest,
    Role,
    WithPermission,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search.fts import decode_cursor, encode_cursor
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.queue import enqueue
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.news.models import (
    Article,
    ArticleRead,
    ArticleRevision,
    ArticleTranslation,
    Category,
)
from portalab.modules.news.permissions import (
    NEWS_ARCHIVE,
    NEWS_CREATE,
    NEWS_DELETE,
    NEWS_MODIFY,
    NEWS_PUBLISH,
    NEWS_READ,
)

PUBLISH_JOB = "news.publish_scheduled"
PAGE = 20
TRANSITIONS = {
    "publish": ({"draft", "scheduled"}, "published"),
    "schedule": ({"draft", "scheduled"}, "scheduled"),
    "unschedule": ({"scheduled"}, "draft"),
    "archive": ({"published"}, "archived"),
    "restore": ({"archived"}, "published"),
}
log = get_logger("portalab.news")


class ArticleNotFound(NotFound):
    default_code = "news.not_found"
    default_title = "Article not found"


class InvalidTransition(Conflict):
    default_code = "news.invalid_transition"
    default_title = "This change is not possible in the article's current state"


def slugify(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")[:120] or "article"


@dataclass
class ArticleInput:
    title: str
    body_md: str
    summary: str = ""
    category_id: UUID | None = None
    audience: dict[str, Any] | None = None
    notify_on_publish: bool = False
    language: str = "en"
    email_on_publish: bool = False  # 027: e-mailed to the channel's subscribers when published


class ArticleService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.authorizer = authorizer
        self.capabilities = capabilities
        self.config = config  # callable → NewsConfig
        self.clock = clock
        # 027: e-mails a published newsletter to its channel's subscribers (set by the module)
        self.newsletter: Callable[[Article], Awaitable[int]] | None = None

    async def allowed(self, principal: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(principal, permission)
        except Exception:
            return False

    async def is_editor(self, principal: Principal) -> bool:
        return await self.allowed(principal, NEWS_CREATE) or await self.allowed(principal, NEWS_MODIFY)

    async def readable(self, article: Article, viewer: Principal) -> bool:
        if article.status == "deleted":
            return False
        if article.status in ("draft", "scheduled"):
            return await self.is_editor(viewer)
        if not await self.allowed(viewer, NEWS_READ):
            return False
        return await self.is_editor(viewer) or await can_read(
            article.audience, viewer, self.authorizer, self.capabilities
        )

    # --- writes ------------------------------------------------------------------------------------------
    async def _slug(self, session: AsyncSession, title: str) -> str:
        base = slugify(title)
        wanted, n = base, 2
        while await session.scalar(select(Article.id).where(Article.slug == wanted)) is not None:
            wanted, n = f"{base}-{n}"[:160], n + 1
        return wanted

    def _vector(self, title: str, summary: str, text: str) -> Any:
        return func.to_tsvector("simple", normalize_for_search(f"{title} {title} {summary} {text}")[:200_000])

    async def create(self, actor: Principal | None, data: ArticleInput) -> Article:
        """``actor=None``: written by the portal itself (an automatic newsletter)."""
        if actor is not None and not await self.allowed(actor, NEWS_CREATE):
            raise Forbidden("You cannot write news.")
        rendered = await render_markdown_async(data.body_md)
        audience = Audience.model_validate(
            data.audience or {"mode": self.config().default_audience}
        ).model_dump()
        now = utc_now(self.clock)
        author = (actor.acting_for or actor.user_id) if actor is not None else None
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await self._category(session, data.category_id)
            row = Article(
                slug=await self._slug(session, data.title),
                language=data.language,
                title=data.title.strip()[:200],
                summary=data.summary.strip()[:600],
                body_md=data.body_md,
                rendered_html=rendered.html,
                renderer_version=rendered.renderer_version,
                plain_text=rendered.text,
                category_id=data.category_id,
                author_id=author,
                status="draft",
                audience=audience,
                notify_on_publish=data.notify_on_publish,
                email_on_publish=data.email_on_publish,
                version=1,
                search_vector=self._vector(data.title, data.summary, rendered.text),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            session.add(self._revision(row, author, now))
            return row

    @staticmethod
    def _revision(row: Article, author: UUID | None, now: datetime) -> ArticleRevision:
        return ArticleRevision(
            article_id=row.id, version=row.version, title=row.title, summary=row.summary, body_md=row.body_md,
            author_id=author, changed_at=now,
        )  # fmt: skip

    async def _category(self, session: AsyncSession, category_id: UUID | None) -> None:
        if category_id is not None:
            category = await session.get(Category, category_id)
            if category is None or not category.enabled:
                raise ValidationFailed("This category does not exist.", code="news.invalid_category")

    async def _for_edit(self, session: AsyncSession, article_id: UUID, actor: Principal) -> Article:
        row = await session.get(Article, article_id, with_for_update=True)
        if row is None or row.status == "deleted" or not await self.readable(row, actor):
            raise ArticleNotFound("This article does not exist.")
        own_draft = row.status == "draft" and row.author_id == (actor.acting_for or actor.user_id)
        if not (
            await self.allowed(actor, NEWS_MODIFY) or (own_draft and await self.allowed(actor, NEWS_CREATE))
        ):
            raise Forbidden("You cannot edit this article.")
        return row

    async def update(
        self, actor: Principal, article_id: UUID, data: ArticleInput, base_version: int | None
    ) -> Article:
        rendered = await render_markdown_async(data.body_md)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            row = await self._for_edit(session, article_id, actor)
            if base_version is not None and base_version != row.version:
                raise Conflict("The article changed since you opened it.", code="news.version_conflict")
            await self._category(session, data.category_id)
            row.title, row.summary, row.body_md = (
                data.title.strip()[:200],
                data.summary.strip()[:600],
                data.body_md,
            )
            row.rendered_html, row.renderer_version, row.plain_text = (
                rendered.html,
                rendered.renderer_version,
                rendered.text,
            )
            row.category_id, row.notify_on_publish, row.language = (
                data.category_id,
                data.notify_on_publish,
                data.language,
            )
            row.email_on_publish = data.email_on_publish
            if data.audience is not None:
                row.audience = Audience.model_validate(data.audience).model_dump()
            row.search_vector = self._vector(row.title, row.summary, rendered.text)
            row.version, row.updated_at = row.version + 1, now
            session.add(self._revision(row, actor.acting_for or actor.user_id, now))
            return row

    async def _event(self, session: AsyncSession, row: Article, action: str) -> None:
        await self.events.publish(
            session,
            f"news.article_{action}",
            {
                "article": str(row.id),
                "publish_seq": row.publish_seq,
                "category": str(row.category_id) if row.category_id else None,
            },
            occurred_at=utc_now(self.clock),
            source="news",
            dedup_key=f"news.{action}:{row.id}:{row.publish_seq}:{row.version}",
        )

    async def transition(
        self, actor: Principal | None, article_id: UUID, action: str, *, publish_at: datetime | None = None
    ) -> Article:
        """``actor=None`` is the scheduler (system)."""
        allowed_from, target = TRANSITIONS[action]
        permission = NEWS_ARCHIVE if action in ("archive", "restore") else NEWS_PUBLISH
        now = utc_now(self.clock)
        notify = email = False
        async with self.database.unit_of_work() as uow:
            session = uow.session
            row = await session.get(Article, article_id, with_for_update=True)
            if (
                row is None
                or row.status == "deleted"
                or (actor is not None and not await self.readable(row, actor))
            ):
                raise ArticleNotFound("This article does not exist.")
            if actor is not None and not await self.allowed(actor, permission):
                raise Forbidden("You cannot change the state of this article.")
            if row.status not in allowed_from:
                raise InvalidTransition(f"An article that is {row.status} cannot be {action}ed.")
            if action == "schedule":
                if publish_at is None or publish_at <= now:
                    raise ValidationFailed(
                        "Choose a publication time in the future.", code="news.invalid_schedule"
                    )
                row.publish_at = publish_at
                await enqueue(
                    session,
                    kind=PUBLISH_JOB,
                    payload={"article": str(row.id), "publish_at": publish_at.isoformat()},
                    dedup_key=f"{PUBLISH_JOB}:{row.id}:{publish_at.isoformat()}",
                    run_at=publish_at,
                    clock=self.clock,
                )
            if action == "unschedule":
                row.publish_at = None
            if action == "publish":
                row.publish_seq += 1
                row.published_at = now
                row.publish_at = None
                notify = row.notify_on_publish
                email = row.email_on_publish and row.emailed_at is None
            if action == "archive":
                row.archived_at = now
            if action == "restore":
                row.archived_at = None
            row.status, row.updated_at = target, now
            event = {"publish": "published", "archive": "archived", "restore": "restored"}.get(action)
            if event:
                await self._event(session, row, event)
        if notify:
            await self._notify(row)
        if email and self.newsletter is not None:
            try:
                await self.newsletter(row)
            except Exception:
                log.warning("newsletter e-mail not sent")  # publishing is never blocked
        return row

    async def run_scheduled(self, payload: dict[str, Any]) -> bool:
        """Job handler: publish once when the article is still scheduled for that very time."""
        async with self.database.session() as session:
            row = await session.get(Article, UUID(str(payload["article"])))
        if row is None or row.status != "scheduled" or row.publish_at is None:
            return False
        try:
            planned = datetime.fromisoformat(str(payload.get("publish_at")))
        except ValueError:
            return False
        if row.publish_at != planned or row.publish_at > utc_now(self.clock):
            return False  # rescheduled since this job was planned
        try:
            await self.transition(None, row.id, "publish")
        except InvalidTransition:
            return False  # another run published it first
        return True

    async def sweep(self) -> int:
        """Safety net: publish scheduled articles whose time passed (jobs lost while the worker was down)."""
        async with self.database.session() as session:
            due = (
                await session.execute(
                    select(Article.id, Article.publish_at).where(
                        Article.status == "scheduled", Article.publish_at <= utc_now(self.clock)
                    )
                )
            ).all()
        done = 0
        for article_id, publish_at in due:
            done += await self.run_scheduled(
                {"article": str(article_id), "publish_at": publish_at.isoformat()}
            )
        return done

    async def feature(
        self, actor: Principal, article_id: UUID, start: datetime | None, end: datetime | None, priority: int
    ) -> Article:
        if not await self.allowed(actor, NEWS_PUBLISH):
            raise Forbidden("You cannot feature articles.")
        if start is not None and end is not None and end <= start:
            raise ValidationFailed("The featuring window ends before it starts.", code="news.invalid_feature")
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Article, article_id, with_for_update=True)
            if row is None or row.status in ("deleted", "archived"):
                raise ArticleNotFound("This article does not exist.")
            row.featured_from = start or utc_now(self.clock)
            row.featured_until, row.feature_priority = end, priority
            row.updated_at = utc_now(self.clock)
            await self._event(uow.session, row, "featured")
            return row

    async def unfeature(self, actor: Principal, article_id: UUID) -> Article:
        if not await self.allowed(actor, NEWS_PUBLISH):
            raise Forbidden("You cannot feature articles.")
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Article, article_id, with_for_update=True)
            if row is None or row.status == "deleted":
                raise ArticleNotFound("This article does not exist.")
            row.featured_from = row.featured_until = None
            row.updated_at = utc_now(self.clock)
            return row

    async def delete(self, actor: Principal, article_id: UUID) -> Article:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Article, article_id, with_for_update=True)
            if row is None or row.status == "deleted" or not await self.readable(row, actor):
                raise ArticleNotFound("This article does not exist.")
            own_draft = row.status == "draft" and row.author_id == (actor.acting_for or actor.user_id)
            if row.status == "published":
                raise InvalidTransition("Archive a published article before deleting it.")
            if not (await self.allowed(actor, NEWS_DELETE) or own_draft):
                raise Forbidden("You cannot delete this article.")
            row.status, row.updated_at = "deleted", utc_now(self.clock)
            row.featured_from = row.featured_until = None
            await self._event(uow.session, row, "deleted")
            return row

    async def translate(
        self, actor: Principal, article_id: UUID, language: str, title: str, summary: str, body: str
    ) -> Article:
        rendered = await render_markdown_async(body)
        async with self.database.unit_of_work() as uow:
            row = await self._for_edit(uow.session, article_id, actor)
            if language == row.language:
                raise ValidationFailed("This is the article's source language.", code="news.invalid_language")
            values = {
                "title": title.strip()[:200], "summary": summary.strip()[:600], "body_md": body,
                "rendered_html": rendered.html, "renderer_version": rendered.renderer_version,
                "state": "translated", "updated_at": utc_now(self.clock),
            }  # fmt: skip
            existing = await uow.session.get(ArticleTranslation, (row.id, language), with_for_update=True)
            if existing is None:
                uow.session.add(ArticleTranslation(article_id=row.id, language=language, **values))
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
            return row

    # --- notifications -------------------------------------------------------------------------------
    async def _notify(self, row: Article) -> None:
        try:
            providers = self.capabilities.system_providers(NOTIFY)
        except Exception:
            return
        if not providers:
            return
        audience = Audience.model_validate(row.audience)
        targets: list[Any] = (
            [AllAuthenticated()]
            if audience.mode == "all"
            else [Role(r) for r in audience.refs]
            if audience.mode == "roles"
            else [WithPermission(p) for p in audience.refs]
        )
        for target in targets:
            label = getattr(target, "role", None) or getattr(target, "permission", None) or "all"
            try:
                await asyncio.wait_for(
                    providers[0].provider.send(
                        CommunicationRequest(
                            category="news.published",
                            template_key="news:notify.published",
                            audience=target,
                            dedup_key=f"news.published:{row.id}:{row.publish_seq}:{label}",
                            params={"title": row.title[:200]},
                            source="module",
                            subject_ref=f"news:{row.id}",
                            required_permission=NEWS_READ,
                            action_url=f"/news/{row.slug}",
                        )
                    ),
                    timeout=10,
                )
            except Exception:
                log.warning("news publication notification not sent")  # publishing is never blocked

    # --- who read what (#48) ----------------------------------------------------------------------------
    async def mark_read(self, viewer: Principal, key: str) -> bool:
        """The member opened a published article: remembered the first time (later visits change nothing)."""
        row = await self.get(key, viewer)
        if row.status != "published" or viewer.user_id is None:
            return False
        async with self.database.unit_of_work() as uow:
            done = await uow.session.execute(
                insert(ArticleRead)
                .values(article_id=row.id, user_id=viewer.user_id, read_at=utc_now(self.clock))
                .on_conflict_do_nothing(index_elements=["article_id", "user_id"])
            )
        return bool(getattr(done, "rowcount", 0))

    async def read_ids(self, user_id: UUID | None, article_ids: Sequence[UUID]) -> set[UUID]:
        """Which of these articles the member has read."""
        if user_id is None or not article_ids:
            return set()
        async with self.database.session() as session:
            rows = await session.execute(
                select(ArticleRead.article_id).where(
                    ArticleRead.user_id == user_id, ArticleRead.article_id.in_(list(article_ids))
                )
            )
            return set(rows.scalars())

    async def read_counts(self, article_ids: Sequence[UUID]) -> dict[UUID, int]:
        if not article_ids:
            return {}
        async with self.database.session() as session:
            rows = await session.execute(
                select(ArticleRead.article_id, func.count())
                .where(ArticleRead.article_id.in_(list(article_ids)))
                .group_by(ArticleRead.article_id)
            )
            return {article: int(count) for article, count in rows}

    async def readers(self, actor: Principal, article_id: UUID) -> dict[str, Any]:
        """For the editors: who opened the article (and when), and the active members who have not."""
        if not await self.is_editor(actor):
            raise Forbidden("You cannot manage news.")
        async with self.database.session() as session:
            row = await session.get(Article, article_id)
            if row is None or row.status == "deleted":
                raise ArticleNotFound("This article does not exist.")
            reads = {
                user: at
                for user, at in await session.execute(
                    select(ArticleRead.user_id, ArticleRead.read_at).where(
                        ArticleRead.article_id == article_id
                    )
                )
            }
        contact = self.capabilities.system_providers(CONTACT)
        members: list[UUID] = []
        if contact:
            try:
                members = list(await contact[0].provider.active_user_ids())
            except Exception:
                members = []
        directory = self.capabilities.system_providers(DIRECTORY)

        async def name(user: UUID) -> str | None:
            if not directory:
                return None
            try:
                summary = await directory[0].provider.get_user_summary(user)
            except Exception:
                return None
            return summary.display_name if summary is not None else None

        read = [
            {"user_id": str(user), "name": await name(user), "read_at": at.isoformat()}
            for user, at in sorted(reads.items(), key=lambda item: item[1], reverse=True)
        ]
        unread = [{"user_id": str(user), "name": await name(user)} for user in members if user not in reads]
        unread.sort(key=lambda item: (item["name"] or "").lower())
        return {"read": read, "unread": unread, "members": len(set(members) | set(reads))}

    # --- reads ---------------------------------------------------------------------------------------
    async def by_key(self, key: str) -> Article | None:
        async with self.database.session() as session:
            try:
                found = await session.get(Article, UUID(key))
                if found is not None:
                    return found
            except ValueError:
                pass
            return (await session.execute(select(Article).where(Article.slug == key))).scalar_one_or_none()

    async def get(self, key: str, viewer: Principal) -> Article:
        row = await self.by_key(key)
        if row is None or not await self.readable(row, viewer):
            raise ArticleNotFound("This article does not exist.")
        if row.renderer_version != RENDERER_VERSION:
            row.rendered_html = (
                await render_markdown_async(row.body_md)
            ).html  # derived cache, refreshed lazily
        return row

    async def translation(self, article: Article, language: str | None) -> ArticleTranslation | None:
        if not language or language == article.language:
            return None
        async with self.database.session() as session:
            row = await session.get(ArticleTranslation, (article.id, language))
        return row if row is not None and row.state == "translated" else None

    async def listing(
        self,
        viewer: Principal,
        *,
        category: str | None = None,
        cursor: str | None = None,
        q: str | None = None,
    ) -> tuple[list[Article], str | None]:
        stmt = select(Article).where(Article.status == "published")
        if category:
            stmt = stmt.join(Category, Category.id == Article.category_id).where(Category.key == category)
        if q:
            stmt = stmt.where(
                Article.search_vector.op("@@")(
                    func.websearch_to_tsquery("simple", normalize_for_search(q)[:300])
                )
            )
        offset = decode_cursor(cursor)
        async with self.database.session() as session:
            rows = (
                (await session.execute(stmt.order_by(Article.published_at.desc(), Article.id).limit(1000)))
                .scalars()
                .all()
            )
        visible = [r for r in rows if await self.readable(r, viewer)]
        page = visible[offset : offset + PAGE]
        return page, encode_cursor(offset + PAGE) if offset + PAGE < len(visible) else None

    async def featured(self, viewer: Principal) -> list[Article]:
        now = utc_now(self.clock)
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(Article)
                        .where(
                            Article.status == "published",
                            Article.featured_from.is_not(None),
                            Article.featured_from <= now,
                            or_(Article.featured_until.is_(None), Article.featured_until > now),
                        )
                        .order_by(Article.feature_priority.desc(), Article.published_at.desc())
                    )
                )
                .scalars()
                .all()
            )
        visible = [r for r in rows if await self.readable(r, viewer)]
        return visible[: max(0, self.config().max_featured)]

    async def editorial(self, viewer: Principal, status: str | None = None) -> list[Article]:
        if not await self.is_editor(viewer):
            raise Forbidden("You cannot manage news.")
        stmt = select(Article).where(Article.status != "deleted")
        if status:
            stmt = stmt.where(Article.status == status)
        async with self.database.session() as session:
            return list(
                (await session.execute(stmt.order_by(Article.updated_at.desc()).limit(200))).scalars().all()
            )

    async def in_range(self, start: datetime, end: datetime, viewer: Principal) -> list[Article]:
        editor = await self.is_editor(viewer)
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(Article).where(
                            or_(
                                and_(
                                    Article.status == "published",
                                    Article.published_at >= start,
                                    Article.published_at < end,
                                ),
                                and_(
                                    Article.status == "scheduled",
                                    Article.publish_at >= start,
                                    Article.publish_at < end,
                                ),
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
        return [r for r in rows if (editor or r.status == "published") and await self.readable(r, viewer)]

    async def categories(self, *, enabled_only: bool = True) -> Sequence[Category]:
        async with self.database.session() as session:
            stmt = select(Category).order_by(Category.position, Category.name)
            if enabled_only:
                stmt = stmt.where(Category.enabled.is_(True))
            return list((await session.execute(stmt)).scalars().all())
