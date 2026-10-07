"""Schema ``connectors`` (specs/005-connectors/data-model.md).

``sync_runs`` rows are immutable: a run row is written once, when the run ends (the live "running" status
is ``sync_state.status``); UPDATE/TRUNCATE are rejected by trigger and only the 021 retention window
deletes. Credentials are an encrypted envelope (``SecretBox``, one token per secret field, bound to the
service id) and are never returned, exported or logged.
"""

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
from portalab.core.privacy_registry import not_personal

SERVICE_STATES = (
    "configured",
    "enabled",
    "syncing",
    "error",
    "unavailable",
    "maintenance",
    "disabled",
    "disconnected",
)
RUN_KINDS = ("scheduled", "manual", "resync_partial", "resync_full")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class ConnectorsBase(DeclarativeBase):
    metadata = schema_metadata("connectors")


IMPORTANCES: tuple[str, ...] = ("critical", "major", "minor", "internal")


class Service(ConnectorsBase):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(_in("state", SERVICE_STATES), name="state"),
        CheckConstraint(_in("importance", IMPORTANCES), name="importance"),
        Index("ix_services_connector_key", "connector_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    connector_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, info=not_personal("service label"))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    credentials: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    state_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state_reason: Mapped[str | None] = mapped_column(String(256))
    state_changed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    enabled_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    disabled_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    disconnected_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    sync_interval_seconds: Mapped[int | None] = mapped_column(Integer)
    # 027: where members open the service (quick links); the connection URL may be internal
    public_url: Mapped[str | None] = mapped_column(
        String(512), info=not_personal("a service's public address")
    )
    # 027: how much the service matters — its outages follow the importance's alerting rules (incident,
    # delays, notifications, e-mails), field by field overridden by ``alerting`` (``{}``: the rules)
    importance: Mapped[str] = mapped_column(
        String(10), nullable=False, default="major", server_default="major"
    )
    alerting: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ServiceCapability(ConnectorsBase):
    __tablename__ = "service_capabilities"
    __table_args__ = (UniqueConstraint("service_id", "capability", name="uq_service_capabilities"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("connectors.services.id", ondelete="CASCADE"), nullable=False
    )
    capability: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)


class SyncState(ConnectorsBase):
    __tablename__ = "sync_state"
    __table_args__ = (CheckConstraint("status IN ('idle', 'running', 'failed')", name="status"),)

    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("connectors.services.id", ondelete="CASCADE"), primary_key=True
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="idle")
    cursor: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    next_run_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 027: how far the running sync got — {"capability", "done", "total", "started_at"}; null when idle
    progress: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class SyncRun(ConnectorsBase):
    __tablename__ = "sync_runs"
    __table_args__ = (
        CheckConstraint(_in("kind", RUN_KINDS), name="kind"),
        CheckConstraint("status IN ('succeeded', 'partial', 'failed')", name="status"),
        Index("ix_sync_runs_service_started", "service_id", "started_at"),
        {"info": APPEND_ONLY_INFO},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    capability: Mapped[str | None] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    triggered_by: Mapped[UUID | None] = mapped_column()
    started_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    modified: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ignored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DiscoveryCandidate(ConnectorsBase):
    __tablename__ = "discovery_candidates"
    __table_args__ = (
        CheckConstraint("status IN ('candidate', 'confirmed', 'declined')", name="status"),
        UniqueConstraint("connector_key", "target", name="uq_discovery_candidates_target"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    connector_key: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(512), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    found_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    service_id: Mapped[UUID | None] = mapped_column()


class CompatibilityCheck(ConnectorsBase):
    __tablename__ = "compatibility_checks"
    __table_args__ = (
        CheckConstraint("result IN ('compatible', 'warning', 'incompatible')", name="result"),
        Index("ix_compatibility_checks_connector", "connector_key", "checked_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    connector_key: Mapped[str] = mapped_column(String(64), nullable=False)
    portal_version: Mapped[str] = mapped_column(String(32), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
