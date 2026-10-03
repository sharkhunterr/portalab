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
from portalab.core.privacy_registry import not_personal


class NewsBase(DeclarativeBase):
    metadata = schema_metadata("news")


class Category(NewsBase):
    __tablename__ = "categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, info=not_personal("category label"))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


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
