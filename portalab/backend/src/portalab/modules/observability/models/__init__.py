"""Schema ``obs`` (specs/025-observability/data-model.md) — the observability store, separate from the
business event store (R6). Minute samples are partitioned by month; ``health_history`` is append-only.
Nothing here holds secrets, personal data beyond an optional user id, or AI conversation content."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal, pii


class ObsBase(DeclarativeBase):
    metadata = schema_metadata("obs")


class ComponentHealth(ObsBase):
    __tablename__ = "component_health"
    __table_args__ = (
        CheckConstraint("technical IN ('ok', 'degraded', 'down', 'unknown')", name="technical"),
        CheckConstraint("functional IN ('ok', 'degraded', 'failing', 'unknown')", name="functional"),
    )

    component: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    technical: Mapped[str] = mapped_column(String(16), nullable=False)
    functional: Mapped[str] = mapped_column(String(16), nullable=False)
    since: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class HealthHistory(ObsBase):
    __tablename__ = "health_history"
    __table_args__ = (
        CheckConstraint("axis IN ('technical', 'functional')", name="axis"),
        Index("ix_health_history_component_occurred", "component", "occurred_at"),
        {"info": APPEND_ONLY_INFO},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    component: Mapped[str] = mapped_column(String(128), nullable=False)
    axis: Mapped[str] = mapped_column(String(16), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(16))
    to_state: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    reason: Mapped[str] = mapped_column(String(256), nullable=False, default="")


class MetricSample(ObsBase):
    """One minute of one metric (counters: count/sum; histograms: count/sum/max/p95)."""

    __tablename__ = "metric_samples"
    __table_args__ = (
        Index("ix_metric_samples_metric", "component", "metric", "sampled_at"),
        {"postgresql_partition_by": "RANGE (sampled_at)"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    sampled_at: Mapped[datetime] = mapped_column(TZDateTime, primary_key=True)
    component: Mapped[str] = mapped_column(String(128), nullable=False)
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    labels: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    sum: Mapped[float] = mapped_column(Float, nullable=False)
    max: Mapped[float | None] = mapped_column(Float)
    p95: Mapped[float | None] = mapped_column(Float)


class Rollup(ObsBase):
    __tablename__ = "rollups"
    __table_args__ = (
        CheckConstraint("bucket_kind IN ('hour', 'day')", name="bucket_kind"),
        UniqueConstraint(
            "component", "metric", "labels_key", "bucket_kind", "bucket", name="uq_rollups_bucket"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    component: Mapped[str] = mapped_column(String(128), nullable=False)
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    labels: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    labels_key: Mapped[str] = mapped_column(String(512), nullable=False)
    bucket_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    bucket: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    sum: Mapped[float] = mapped_column(Float, nullable=False)
    p95: Mapped[float | None] = mapped_column(Float)
    max: Mapped[float | None] = mapped_column(Float)


class ErrorRecord(ObsBase):
    __tablename__ = "errors"
    __table_args__ = (
        CheckConstraint("state IN ('open', 'acknowledged', 'resolved')", name="state"),
        UniqueConstraint("fingerprint", name="uq_errors_fingerprint"),
        Index("ix_errors_state_last_seen", "state", "last_seen_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    component: Mapped[str] = mapped_column(String(128), nullable=False)
    service_ref: Mapped[str | None] = mapped_column(String(64))
    plugin_ref: Mapped[str | None] = mapped_column(String(128))
    event_ref: Mapped[str | None] = mapped_column(String(64))
    user_ref: Mapped[UUID | None] = mapped_column(info=pii("identifier"))
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    error_type: Mapped[str] = mapped_column(String(128), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(
        Text, nullable=False, info=not_personal("redacted technical message")
    )
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    resolution: Mapped[str | None] = mapped_column(Text, info=not_personal("operator resolution note"))
    resolved_by: Mapped[UUID | None] = mapped_column()
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class Anomaly(ObsBase):
    __tablename__ = "anomalies"
    __table_args__ = (
        CheckConstraint(
            "status IN ('candidate', 'pending_validation', 'escalated', 'dismissed', 'resolved')",
            name="status",
        ),
        CheckConstraint("severity IN ('info', 'warning', 'critical')", name="severity"),
        Index("ix_anomalies_fingerprint_status", "fingerprint", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    detector: Mapped[str] = mapped_column(String(64), nullable=False)
    component: Mapped[str] = mapped_column(String(128), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    incident_ref: Mapped[str | None] = mapped_column(String(64))
    validated_by: Mapped[UUID | None] = mapped_column()
    escalation_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Contribution(ObsBase):
    __tablename__ = "contributions"

    contribution_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    declared_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LogEntry(ObsBase):
    """Issue 158: one line of the server's or the worker's log, already redacted (``core.logging``), kept a
    few days for the administrators' journal (bounded by age and by count)."""

    __tablename__ = "log_entries"
    __table_args__ = (
        Index("ix_log_entries_at", "at"),
        Index("ix_log_entries_correlation", "correlation_id"),
        Index("ix_log_entries_source_seq", "source", "seq"),
    )

    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    process: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    logger: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(
        Text, nullable=False, info=not_personal("redacted technical log line")
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    fields: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, info=not_personal("redacted structured log fields")
    )
