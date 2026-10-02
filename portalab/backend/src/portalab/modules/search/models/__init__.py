"""Schema ``search`` (specs/008-search-command-palette/data-model.md): private search history (personal
data, class ``activity``) and operational index state. The semantic ``embeddings`` table (ids + vectors,
no text) exists only when pgvector is available and is not modelled here (raw SQL, rebuildable)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import pii


class SearchBase(DeclarativeBase):
    metadata = schema_metadata("search")


class SearchHistory(SearchBase):
    __tablename__ = "history"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_query", name="uq_history_user_query"),
        CheckConstraint("mode IN ('exact', 'semantic', 'mixed')", name="mode"),
        Index("ix_history_user_performed", "user_id", "performed_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    query_text: Mapped[str] = mapped_column(String(512), nullable=False, info=pii("activity", tombstone=""))
    normalized_query: Mapped[str] = mapped_column(
        String(512), nullable=False, info=pii("activity", tombstone="")
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, info=pii("activity", tombstone={}))
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    performed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class IndexState(SearchBase):
    __tablename__ = "index_state"

    kind: Mapped[str] = mapped_column(String(96), primary_key=True)
    last_full_reindex_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    last_indexed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    pending_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
