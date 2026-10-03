"""Schema ``media`` (specs/024-media/data-model.md). Objects are never deleted when a source disappears;
``service_id`` and source references are opaque (no FK outside the module except ``identity.users``)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import pii

# ``user_id`` columns reference ``identity.users(id)`` through foreign keys created in the migration only.


class MediaBase(DeclarativeBase):
    metadata = schema_metadata("media")


class MediaObject(MediaBase):
    __tablename__ = "objects"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'hidden', 'merged')", name="status"),
        Index("ix_objects_kind_title", "kind", "sort_title"),
        Index("ix_objects_parent", "parent_id", "position"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.objects.id"))
    position: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_title: Mapped[str] = mapped_column(String(500), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    field_provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    merged_into: Mapped[UUID | None] = mapped_column(ForeignKey("media.objects.id"))
    first_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ExternalId(MediaBase):
    __tablename__ = "external_ids"
    __table_args__ = (Index("ix_external_ids_object", "object_id"),)

    scheme: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), primary_key=True)
    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), nullable=False)


class SourceItem(MediaBase):
    __tablename__ = "source_items"
    __table_args__ = (
        UniqueConstraint("service_id", "external_id", name="uq_source_items_service_external"),
        CheckConstraint("availability IN ('available', 'unavailable', 'unknown')", name="availability"),
        Index("ix_source_items_object", "object_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    object_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.objects.id"))
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    availability: Mapped[str] = mapped_column(String(12), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class FieldCandidate(MediaBase):
    __tablename__ = "field_candidates"

    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), primary_key=True)
    field: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_system: Mapped[str] = mapped_column(String(120), primary_key=True)  # ``admin`` = override
    source_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.source_items.id"))
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ObjectTag(MediaBase):
    __tablename__ = "object_tags"
    __table_args__ = (
        CheckConstraint("tag_kind IN ('genre', 'tag', 'keyword', 'person')", name="tag_kind"),
        Index("ix_object_tags_value", "tag_kind", "value"),
    )

    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), primary_key=True)
    tag_kind: Mapped[str] = mapped_column(String(10), primary_key=True)
    value: Mapped[str] = mapped_column(String(120), primary_key=True)


class MatchCandidate(MediaBase):
    __tablename__ = "match_candidates"
    __table_args__ = (
        UniqueConstraint("object_a", "object_b", name="uq_match_candidates_pair"),
        CheckConstraint("state IN ('proposed', 'accepted', 'rejected')", name="state"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    object_a: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), nullable=False)
    object_b: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class MergeLog(MediaBase):
    """Append-only: every merge/split with the pointers needed to reverse it."""

    __tablename__ = "merge_log"
    __table_args__ = (CheckConstraint("action IN ('merge', 'split')", name="action"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    object_id: Mapped[UUID] = mapped_column(nullable=False)  # surviving / restored object
    other_id: Mapped[UUID] = mapped_column(nullable=False)  # merged-away / split-off object
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Image(MediaBase):
    __tablename__ = "images"
    __table_args__ = (
        UniqueConstraint("object_id", "role", name="uq_images_object_role"),
        CheckConstraint("role IN ('poster', 'backdrop', 'thumb')", name="role"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    blob_key: Mapped[str] = mapped_column(String(200), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(300), nullable=False)
    source_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.source_items.id"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class UserLink(MediaBase):
    __tablename__ = "user_links"
    __table_args__ = (
        UniqueConstraint("service_id", "external_user_id", name="uq_user_links_external"),
        UniqueConstraint("user_id", "service_id", name="uq_user_links_user_service"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    external_user_id: Mapped[str] = mapped_column(
        String(200), nullable=False, info=pii("identifier", tombstone="erased")
    )
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class PlaybackSession(MediaBase):
    __tablename__ = "playback_sessions"
    __table_args__ = (
        CheckConstraint(
            "state IN ('playing', 'paused', 'buffering', 'stopped', 'stale', 'interrupted')", name="state"
        ),
        Index("ix_playback_sessions_user", "user_id", "updated_at"),
    )

    session_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID | None] = mapped_column()
    external_user_id: Mapped[str | None] = mapped_column(String(200), info=pii("activity"))
    object_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.objects.id"))
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    position_s: Mapped[float] = mapped_column(Float, nullable=False)
    max_position_s: Mapped[float] = mapped_column(Float, nullable=False)
    duration_s: Mapped[float | None] = mapped_column(Float)
    device: Mapped[str | None] = mapped_column(String(120), info=pii("activity"))
    started_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    as_of: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    last_event_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    state_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    ended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class HistoryEntry(MediaBase):
    """Rebuildable projection of playback events (the 007 event stream is the record)."""

    __tablename__ = "history_entries"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_history_entries_event"),
        CheckConstraint("kind IN ('session', 'progress', 'finished')", name="kind"),
        Index("ix_history_entries_user", "user_id", "occurred_at"),
        Index("ix_history_entries_object", "object_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    event_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    session_key: Mapped[str | None] = mapped_column(String(300))
    position_from_s: Mapped[float] = mapped_column(Float, nullable=False)
    position_to_s: Mapped[float] = mapped_column(Float, nullable=False)
    consumed_s: Mapped[float] = mapped_column(Float, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class UserProgress(MediaBase):
    __tablename__ = "user_progress"
    __table_args__ = (CheckConstraint("state IN ('in_progress', 'finished')", name="state"),)

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    object_id: Mapped[UUID] = mapped_column(ForeignKey("media.objects.id"), primary_key=True)
    resume_position_s: Mapped[float] = mapped_column(Float, nullable=False)
    percent: Mapped[float] = mapped_column(Float, nullable=False)
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    last_occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class QuotaUnits(MediaBase):
    __tablename__ = "request_quota_units"
    __table_args__ = (CheckConstraint("units_remaining >= 0", name="units_remaining"),)

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    units_remaining: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class QuotaLedger(MediaBase):
    """Append-only ledger of extra request units (credited by 015, consumed by requests)."""

    __tablename__ = "request_quota_ledger"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_request_quota_ledger_idempotency"),
        CheckConstraint("reason IN ('purchase', 'refund', 'consumption', 'admin')", name="reason"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    delta: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(12), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class MediaRequest(MediaBase):
    __tablename__ = "requests"
    __table_args__ = (
        UniqueConstraint("service_id", "external_request_id", name="uq_requests_service_external"),
        UniqueConstraint("idempotency_key", name="uq_requests_idempotency"),
        CheckConstraint(
            "state IN ('pending', 'approved', 'declined', 'processing', 'available', 'failed', 'cancelled')",
            name="state",
        ),
        Index("ix_requests_requester", "requester_user_id", "requested_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    object_id: Mapped[UUID | None] = mapped_column(ForeignKey("media.objects.id"))
    external_ref: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # ids, kind, title
    requester_user_id: Mapped[UUID | None] = mapped_column()
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    external_request_id: Mapped[str | None] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    source_state: Mapped[str] = mapped_column(String(60), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    counted: Mapped[str] = mapped_column(String(10), nullable=False)  # ``base`` or ``extra`` quota
    requested_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
