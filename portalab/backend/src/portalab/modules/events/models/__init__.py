"""Schema ``events`` (specs/007-events-history/data-model.md).

``events.events`` is the single append-only history: partitioned by LIST on ``retention_class``
(``events_business`` / ``events_technical``), each sub-partitioned by month on ``occurred_at`` so the two
retention windows are applied by dropping partitions (R5 of 021). Deduplication lives in ``dedup_keys``
because a partitioned table cannot hold a global unique index (R3). Payloads hold ids and facts only.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Identity, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id


class EventsBase(DeclarativeBase):
    metadata = schema_metadata("events")


class Event(EventsBase):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("retention_class IN ('business', 'technical')", name="retention_class"),
        CheckConstraint("actor_kind IN ('user', 'system', 'ai', 'automation', 'plugin')", name="actor_kind"),
        Index("ix_events_seq", "seq"),
        Index("ix_events_type_occurred_at", "type", "occurred_at"),
        Index("ix_events_subject", "subject_type", "subject_id", "occurred_at"),
        Index("ix_events_actor_user_id", "actor_user_id", "occurred_at"),
        {"info": APPEND_ONLY_INFO, "postgresql_partition_by": "LIST (retention_class)"},
    )

    event_id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    retention_class: Mapped[str] = mapped_column(String(16), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False)
    type: Mapped[str] = mapped_column(String(128), nullable=False)
    type_version: Mapped[int] = mapped_column(Integer, nullable=False)
    received_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    source_system: Mapped[str] = mapped_column(String(128), nullable=False)
    source_event_id: Mapped[str | None] = mapped_column(String(256))
    source_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    actor_user_id: Mapped[UUID | None] = mapped_column()
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_type: Mapped[str | None] = mapped_column(String(64))
    subject_id: Mapped[str | None] = mapped_column(String(128))
    service_id: Mapped[str | None] = mapped_column(String(128))
    object_seq: Mapped[int | None] = mapped_column(BigInteger)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    visibility_class: Mapped[str] = mapped_column(String(16), nullable=False)


class DedupKey(EventsBase):
    __tablename__ = "dedup_keys"
    __table_args__ = (Index("ix_dedup_keys_first_seen_at", "first_seen_at"),)

    type: Mapped[str] = mapped_column(String(128), primary_key=True)
    dedup_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Quarantine(EventsBase):
    __tablename__ = "quarantine"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('unknown_type', 'invalid_payload', 'version_unsupported', 'pii_detected')",
            name="reason",
        ),
        CheckConstraint("status IN ('open', 'released', 'discarded')", name="status"),
        Index("ix_quarantine_status", "status", "received_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    received_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_system: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    resolved_by: Mapped[UUID | None] = mapped_column()
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class ConsumerOffset(EventsBase):
    __tablename__ = "consumer_offsets"

    consumer: Mapped[str] = mapped_column(String(128), primary_key=True)
    last_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Delivery(EventsBase):
    __tablename__ = "deliveries"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'succeeded', 'failed', 'dead')", name="status"),
        Index("ix_deliveries_status", "status", "updated_at"),
    )

    consumer: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    event_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(512))
    next_attempt_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class EffectKey(EventsBase):
    __tablename__ = "effect_keys"

    consumer: Mapped[str] = mapped_column(String(128), primary_key=True)
    effect_key: Mapped[str] = mapped_column(String(256), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ReplayRun(EventsBase):
    __tablename__ = "replay_runs"
    __table_args__ = (CheckConstraint("status IN ('running', 'finished', 'failed')", name="status"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    projection: Mapped[str] = mapped_column(String(128), nullable=False)
    from_occurred_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    to_occurred_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    requested_by: Mapped[UUID | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TZDateTime)
