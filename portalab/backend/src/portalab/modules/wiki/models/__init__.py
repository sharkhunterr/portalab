"""Schema ``wiki`` (specs/011 data-model): pages with an append-only revision history (only the rendered
cache and an erased author may change on a revision), tags, derived links and translations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal


class WikiBase(DeclarativeBase):
    metadata = schema_metadata("wiki")


class Page(WikiBase):
    __tablename__ = "pages"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'archived', 'deleted')", name="status"),
        Index("ix_pages_parent", "parent_id", "position"),
        Index("ix_pages_search", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("wiki.pages.id"))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("page title"))
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    audience: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    readable_by_ai: Mapped[bool] = mapped_column(Boolean, nullable=False)
    help_keys: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    search_vector: Mapped[Any] = mapped_column(TSVECTOR, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column()  # FK identity.users (migration), SET NULL
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Revision(WikiBase):
    __tablename__ = "revisions"

    page_id: Mapped[UUID] = mapped_column(ForeignKey("wiki.pages.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("page title"))
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_html: Mapped[str] = mapped_column(Text, nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(8), nullable=False)
    plain_text: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[UUID | None] = mapped_column()  # tombstoned (NULL) on erasure
    change_note: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    restored_from_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class PageTag(WikiBase):
    __tablename__ = "page_tags"
    __table_args__ = (Index("ix_page_tags_tag", "tag"),)

    page_id: Mapped[UUID] = mapped_column(ForeignKey("wiki.pages.id"), primary_key=True)
    tag: Mapped[str] = mapped_column(String(60), primary_key=True)


class PageLink(WikiBase):
    __tablename__ = "page_links"
    __table_args__ = (Index("ix_page_links_target", "target_ref"),)

    from_page_id: Mapped[UUID] = mapped_column(ForeignKey("wiki.pages.id"), primary_key=True)
    target_ref: Mapped[str] = mapped_column(String(260), primary_key=True)


class PageTranslation(WikiBase):
    __tablename__ = "page_translations"
    __table_args__ = (
        CheckConstraint("state IN ('translated', 'machine_draft')", name="state"),
        ForeignKeyConstraint(["page_id"], ["wiki.pages.id"], name="fk_page_translations_page_id_pages"),
    )

    page_id: Mapped[UUID] = mapped_column(primary_key=True)
    language: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("page title"))
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_html: Mapped[str] = mapped_column(Text, nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(8), nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(14), nullable=False)
    updated_by: Mapped[UUID | None] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
