"""Schema ``news`` (specs/011 data-model): categories, articles with their editorial state, append-only
revisions (only an erased author may be tombstoned) and translations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal, pii


class NewsBase(DeclarativeBase):
    metadata = schema_metadata("news")


class Category(NewsBase):
    __tablename__ = "categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, info=not_personal("category label"))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 027: a category is a channel — described, with an icon, and (``newsletter``) e-mailed to its
    # subscribers (members may unsubscribe from each channel)
    description: Mapped[str] = mapped_column(
        String(300), nullable=False, default="", server_default="", info=not_personal("channel description")
    )
    icon: Mapped[str | None] = mapped_column(String(40))
    newsletter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class Article(NewsBase):
    __tablename__ = "articles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'scheduled', 'published', 'archived', 'deleted')", name="status"
        ),
        Index("ix_articles_published", "status", "published_at"),
        Index("ix_articles_search", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("article title"))
    summary: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_html: Mapped[str] = mapped_column(Text, nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(8), nullable=False)
    plain_text: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("news.categories.id"))
    author_id: Mapped[UUID | None] = mapped_column()  # FK identity.users (migration), SET NULL
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    audience: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    publish_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    published_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    archived_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    featured_from: Mapped[datetime | None] = mapped_column(TZDateTime)
    featured_until: Mapped[datetime | None] = mapped_column(TZDateTime)
    feature_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notify_on_publish: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 027: e-mailed to the channel's subscribers when published (once: ``emailed_at``)
    email_on_publish: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        info=not_personal("whether the article is e-mailed on publication"),
    )
    emailed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    publish_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    search_vector: Mapped[Any] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ArticleRevision(NewsBase):
    __tablename__ = "article_revisions"

    article_id: Mapped[UUID] = mapped_column(ForeignKey("news.articles.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("article title"))
    summary: Mapped[str] = mapped_column(String(600), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[UUID | None] = mapped_column()  # tombstoned (NULL) on erasure
    changed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ArticleTranslation(NewsBase):
    __tablename__ = "article_translations"
    __table_args__ = (CheckConstraint("state IN ('translated', 'machine_draft')", name="state"),)

    article_id: Mapped[UUID] = mapped_column(ForeignKey("news.articles.id"), primary_key=True)
    language: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("article title"))
    summary: Mapped[str] = mapped_column(String(600), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_html: Mapped[str] = mapped_column(Text, nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(8), nullable=False)
    state: Mapped[str] = mapped_column(String(14), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ArticleRead(NewsBase):
    """#48: a member opened a published article (the first time) — for the unread dot and the editors'
    « who read it »."""

    __tablename__ = "article_reads"
    __table_args__ = (Index("ix_article_reads_user", "user_id"),)

    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("news.articles.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(primary_key=True, info=pii("activity"))
    # the row is deleted with the member (``user_id`` is the personal part)
    read_at: Mapped[datetime] = mapped_column(
        TZDateTime, nullable=False, info=not_personal("when it was opened, deleted with the member")
    )


class NewsletterSchedule(NewsBase):
    """027: an automatic newsletter — on its cadence the portal writes an article for a channel from what
    the media services report (releases, additions, upcoming) and publishes it (e-mailed when asked)."""

    __tablename__ = "newsletter_schedules"
    __table_args__ = (
        CheckConstraint("kind IN ('releases', 'additions', 'upcoming')", name="kind"),
        CheckConstraint("cadence IN ('daily', 'weekly', 'monthly')", name="cadence"),
        CheckConstraint("weekday BETWEEN 0 AND 6 AND hour BETWEEN 0 AND 23", name="when"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False, info=not_personal("schedule name"))
    category_id: Mapped[UUID] = mapped_column(ForeignKey("news.categories.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    media_kinds: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)  # empty: all
    cadence: Mapped[str] = mapped_column(String(10), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0 = Monday
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="fr")
    email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, info=not_personal("whether the newsletter is e-mailed")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    next_run_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    last_article_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
