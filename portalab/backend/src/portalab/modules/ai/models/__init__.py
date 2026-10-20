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


class Feedback(AiBase):
    """Issue 176: the member's verdict on one answer — as expected (+1) or not (-1), with a word on why. An
    answer rated is shown to the administrators (question, answer, tools) to improve the assistant: the
    member is told so when rating. Gone with the conversation."""

    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("rating IN (-1, 1)", name="rating"),
        Index("ix_feedback_rating", "rating", "updated_at"),
    )

    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai.messages.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(nullable=False)  # FK identity.users (migration), CASCADE
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="", info=pii("content", tombstone=""))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Perk(AiBase):
    """Issue 173: a capacity of the assistant a member bought (or was given) in the shop — more tokens a day,
    a recharge (``remaining`` spent past the day's allowance), a stronger model, more reflection, a longer
    memory, reserved tools — until ``expires_at`` (none: for good). One per purchase (``source_ref``)."""

    __tablename__ = "perks"
    __table_args__ = (
        UniqueConstraint("source_ref"),
        Index("ix_perks_user_id", "user_id", "perk"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)  # FK identity.users (migration), CASCADE
    perk: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(TZDateTime)
