"""Schema ``community`` (specs/012 data-model): the feed projection (rebuildable, ids/params only), community
events, the owners' visibility preferences for Community datum classes (slice A); proposals, votes with
their transactional counters, participations and the append-only recognition and moderation logs
(slice D). Users are referenced by id (FK in the migration only)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
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


class Proposal(CommunityBase):
    """A project or feature proposal (Idea stage, CD-008). Its lifecycle **state** lives in Marketplace
    (015), reached through ``lifecycle_ref``; Community never stores it."""

    __tablename__ = "proposals"
    __table_args__ = (
        CheckConstraint("kind IN ('project', 'feature')", name="kind"),
        CheckConstraint("status IN ('pending_moderation', 'open', 'withdrawn', 'rejected')", name="status"),
        Index("ix_proposals_status", "status", "created_at"),
        Index("ix_proposals_proposer", "proposer_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    provenance_ref: Mapped[str | None] = mapped_column(String(200), unique=True)
    proposer_id: Mapped[UUID | None] = mapped_column()
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, info=not_personal("a public proposal title")
    )
    body_md: Mapped[str] = mapped_column(Text, nullable=False, info=not_personal("a public proposal text"))
    rendered_html: Mapped[str] = mapped_column(Text, nullable=False, info=not_personal("rendered proposal"))
    renderer_version: Mapped[str] = mapped_column(String(16), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    help_wanted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    help_note: Mapped[str | None] = mapped_column(String(500), info=not_personal("a public call for help"))
    lifecycle_ref: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Vote(CommunityBase):
    """One active up-vote per (proposal, account); a retracted vote keeps its row (``retracted_at``)."""

    __tablename__ = "votes"
    __table_args__ = (
        Index(
            "uq_votes_active",
            "proposal_id",
            "user_id",
            unique=True,
            postgresql_where=text("retracted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    proposal_id: Mapped[UUID] = mapped_column(ForeignKey("community.proposals.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    cast_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    retracted_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class VoteCount(CommunityBase):
    __tablename__ = "vote_counts"

    proposal_id: Mapped[UUID] = mapped_column(ForeignKey("community.proposals.id"), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Participation(CommunityBase):
    __tablename__ = "participations"
    __table_args__ = (
        CheckConstraint("role IN ('contributor', 'tester', 'helper')", name="role"),
        CheckConstraint("status IN ('active', 'withdrawn')", name="status"),
        UniqueConstraint("proposal_id", "user_id", "role", name="uq_participations"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    proposal_id: Mapped[UUID] = mapped_column(ForeignKey("community.proposals.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), info=not_personal("a public participation note"))
    recognized_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    recognized_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class RecognitionLog(CommunityBase):
    __tablename__ = "recognition_log"
    __table_args__ = (
        Index("ix_recognition_log_recognizer", "recognizer_id", "created_at"),
        {"info": APPEND_ONLY_INFO},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    participation_id: Mapped[UUID] = mapped_column(ForeignKey("community.participations.id"), nullable=False)
    recognizer_id: Mapped[UUID] = mapped_column(nullable=False)
    recipient_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ModerationLog(CommunityBase):
    __tablename__ = "moderation_log"
    __table_args__ = (
        CheckConstraint("decision IN ('approved', 'rejected')", name="decision"),
        {"info": APPEND_ONLY_INFO},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    proposal_id: Mapped[UUID] = mapped_column(ForeignKey("community.proposals.id"), nullable=False)
    moderator_id: Mapped[UUID | None] = mapped_column()
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), info=not_personal("a moderator's public reason"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
