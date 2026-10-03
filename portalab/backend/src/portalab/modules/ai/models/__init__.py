"""Schema ``ai`` (specs/018 data-model): owner-only conversations and messages (personal ``content``),
pending sensitive actions, per-user daily usage aggregates."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import pii


class AiBase(DeclarativeBase):
    metadata = schema_metadata("ai")


class Conversation(AiBase):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user", "user_id", "updated_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)  # FK identity.users (migration), CASCADE
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=pii("content", tombstone=""))
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Message(AiBase):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "seq", name="uq_messages_seq"),
        CheckConstraint("role IN ('user', 'assistant', 'tool')", name="role"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai.conversations.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, info=pii("content", tombstone=""))
    blocks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, info=pii("content", tombstone={}))
    usage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class PendingAction(AiBase):
    __tablename__ = "pending_actions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'declined', 'expired', 'executed', 'failed')", name="status"
        ),
        Index("ix_pending_actions_user", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)  # FK identity.users (migration), CASCADE
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.conversations.id", ondelete="SET NULL")
    )
    tool: Mapped[str] = mapped_column(String(120), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, info=pii("content", tombstone={}))
    params_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(String(400), nullable=False, info=pii("content", tombstone=""))
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class UsageDaily(AiBase):
    __tablename__ = "usage_daily"

    user_id: Mapped[UUID] = mapped_column(primary_key=True)  # FK identity.users (migration), CASCADE
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
