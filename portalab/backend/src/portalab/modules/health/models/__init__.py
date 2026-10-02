"""Schema ``health`` (specs/006-services-health/data-model.md).

``service_id`` is the logical id of a ``connectors.services`` row (no cross-module FK). Samples are
partitioned by month and thinned by dropping partitions; ``state_history`` is append-only.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal

STATES = ("operational", "degraded", "unavailable", "maintenance", "unknown")
_STATES_SQL = ", ".join(repr(s) for s in STATES)


class HealthBase(DeclarativeBase):
    metadata = schema_metadata("health")


class ServiceState(HealthBase):
    __tablename__ = "service_state"
    __table_args__ = (CheckConstraint(f"state IN ({_STATES_SQL})", name="state"),)

    service_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    state_since: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    state_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_check_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    last_ok_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    maintenance_id: Mapped[UUID | None] = mapped_column()
    rules_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class StateHistory(HealthBase):
    __tablename__ = "state_history"
    __table_args__ = (
        Index("ix_state_history_service_occurred", "service_id", "occurred_at"),
        {"info": APPEND_ONLY_INFO},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    service_id: Mapped[str] = mapped_column(String(64), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(16))
    to_state: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)


class HealthSample(HealthBase):
    __tablename__ = "health_samples"
    __table_args__ = (
        Index("ix_health_samples_service_checked", "service_id", "checked_at"),
        {"postgresql_partition_by": "RANGE (checked_at)"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    checked_at: Mapped[datetime] = mapped_column(TZDateTime, primary_key=True)
    service_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    error_code: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class HealthRollup(HealthBase):
    __tablename__ = "health_rollups"
    __table_args__ = (UniqueConstraint("service_id", "bucket_start", name="uq_health_rollups_bucket"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    service_id: Mapped[str] = mapped_column(String(64), nullable=False)
    bucket_start: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    samples: Mapped[int] = mapped_column(Integer, nullable=False)
    ok_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    p95_latency_ms: Mapped[float | None] = mapped_column(Float)
    downtime_seconds: Mapped[int] = mapped_column(Integer, nullable=False)


class RecentError(HealthBase):
    __tablename__ = "recent_errors"
    __table_args__ = (UniqueConstraint("service_id", "code", name="uq_recent_errors_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    service_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, info=not_personal("redacted technical error"))
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class MaintenanceWindow(HealthBase):
    __tablename__ = "maintenance_windows"
    __table_args__ = (
        CheckConstraint("status IN ('scheduled', 'active', 'ended', 'cancelled')", name="status"),
        CheckConstraint("ends_at > starts_at", name="ordered"),
        Index("ix_maintenance_windows_service", "service_id", "starts_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    service_id: Mapped[str | None] = mapped_column(String(64))  # null = portal-wide
    title: Mapped[str] = mapped_column(String(160), nullable=False, info=not_personal("maintenance title"))
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    starts_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    reference_time_zone: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    schedule_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class InfraSample(HealthBase):
    __tablename__ = "infra_samples"
    __table_args__ = (
        Index("ix_infra_samples_service_metric", "service_id", "metric", "sampled_at"),
        {"postgresql_partition_by": "RANGE (sampled_at)"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    sampled_at: Mapped[datetime] = mapped_column(TZDateTime, primary_key=True)
    service_id: Mapped[str] = mapped_column(String(64), nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(16))
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ServiceIncidentLink(HealthBase):
    __tablename__ = "service_incident_links"
    __table_args__ = (UniqueConstraint("service_id", "incident_id", name="uq_service_incident_links"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    service_id: Mapped[str] = mapped_column(String(64), nullable=False)
    incident_id: Mapped[str] = mapped_column(String(64), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
