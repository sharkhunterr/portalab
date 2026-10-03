"""Schema ``community`` (specs/012 data-model, slice A): the feed projection (rebuildable, ids/params only),
community events, and the owners' visibility preferences for Community datum classes. Users are referenced
by id (FK in the migration only)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal, pii


class CommunityBase(DeclarativeBase):
    metadata = schema_metadata("community")


class FeedEntry(CommunityBase):
    __tablename__ = "feed_entries"
    __table_args__ = (
        CheckConstraint("visibility_class IN ('public', 'community')", name="visibility_class"),
        Index("ix_feed_entries_time", "occurred_at"),
        Index("ix_feed_entries_actor", "actor_user_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    source_event_id: Mapped[UUID] = mapped_column(nullable=False, unique=True)
    actor_user_id: Mapped[UUID] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_ref: Mapped[str | None] = mapped_column(String(200))
    text_key: Mapped[str] = mapped_column(String(160), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    visibility_class: Mapped[str] = mapped_column(String(10), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class CommunityEvent(CommunityBase):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("status IN ('scheduled', 'cancelled')", name="status"),
        CheckConstraint("audience IN ('public', 'community', 'roles')", name="audience"),
        Index("ix_events_window", "starts_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("a public event title"))
    description_md: Mapped[str] = mapped_column(
        Text, nullable=False, info=not_personal("a public event description")
    )
    rendered_html: Mapped[str] = mapped_column(
        Text, nullable=False, info=not_personal("rendered description")
    )
    starts_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reference_tz: Mapped[str] = mapped_column(String(64), nullable=False)
    audience: Mapped[str] = mapped_column(String(10), nullable=False)
    audience_roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    organizer_id: Mapped[UUID | None] = mapped_column(info=pii("identifier"))
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class VisibilityPreference(CommunityBase):
    """Owner-held level for Community datum classes (``member_listing``, ``community_activity``…)."""

    __tablename__ = "visibility_preferences"
    __table_args__ = (
        CheckConstraint("level IN ('public', 'community', 'leaderboard', 'private')", name="level"),
    )

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    datum_class: Mapped[str] = mapped_column(String(40), primary_key=True)
    level: Mapped[str] = mapped_column(String(12), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
