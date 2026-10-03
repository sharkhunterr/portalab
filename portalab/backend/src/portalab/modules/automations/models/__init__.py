"""Schema ``automations`` (specs/019 data-model): automations, append-only versions, executions (references
and counters only — never trigger bodies or secrets), approvals, schedule state, pending relative fires and
dedup windows. Users are referenced by id (FK in the migration only)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal

STATUSES = (
    "running",
    "success",
    "no_op",
    "refused",
    "prevented",
    "timeout",
    "suspended",
    "failed",
    "throttled",
    "awaiting_approval",
)


class AutomationsBase(DeclarativeBase):
    metadata = schema_metadata("automations")


class Automation(AutomationsBase):
    __tablename__ = "automations"
    __table_args__ = (
        CheckConstraint("state IN ('draft', 'active', 'paused', 'suspended', 'archived')", name="state"),
        CheckConstraint("identity_kind IN ('author', 'system')", name="identity_kind"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, info=not_personal("an automation's title"))
    state: Mapped[str] = mapped_column(String(10), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    published_version: Mapped[int | None] = mapped_column(Integer)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    identity_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    system_scopes: Mapped[list[str] | None] = mapped_column(JSONB)
    needs_review: Mapped[bool] = mapped_column(nullable=False, default=False)
    suspend_reason: Mapped[str | None] = mapped_column(String(200))
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class AutomationVersion(AutomationsBase):
    __tablename__ = "versions"
    __table_args__ = ({"info": APPEND_ONLY_INFO},)

    automation_id: Mapped[UUID] = mapped_column(ForeignKey("automations.automations.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    published_by: Mapped[UUID | None] = mapped_column()
    published_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    standing_approvals: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


class Execution(AutomationsBase):
    __tablename__ = "executions"
    __table_args__ = (
        CheckConstraint("status IN (" + ", ".join(f"'{s}'" for s in STATUSES) + ")", name="status"),
        Index(
            "uq_executions_trigger",
            "automation_id",
            "version",
            "trigger_event_id",
            unique=True,
            postgresql_where=text("trigger_event_id IS NOT NULL"),
        ),
        Index("ix_executions_automation", "automation_id", "started_at"),
        Index("ix_executions_chain", "chain_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    automation_id: Mapped[UUID] = mapped_column(
        ForeignKey("automations.automations.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_event_id: Mapped[UUID | None] = mapped_column()
    trigger_ref: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    chain_id: Mapped[str] = mapped_column(String(64), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    conditions_trace: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    batch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    principal: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class Approval(AutomationsBase):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'expired')", name="status"),
        UniqueConstraint("execution_id", "step_id", name="uq_approvals_step"),
        Index("ix_approvals_status", "status", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("automations.executions.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    summary: Mapped[str] = mapped_column(
        String(400), nullable=False, info=not_personal("action-generated summary")
    )
    params_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    decided_by: Mapped[UUID | None] = mapped_column()
    decided_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ScheduleState(AutomationsBase):
    __tablename__ = "schedule_state"

    automation_id: Mapped[UUID] = mapped_column(
        ForeignKey("automations.automations.id", ondelete="CASCADE"), primary_key=True
    )
    next_fire_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    last_fired_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class PendingFire(AutomationsBase):
    """A ``relative`` trigger scheduled from a source event (e.g. maintenance start minus 1 h)."""

    __tablename__ = "pending_fires"
    __table_args__ = (
        UniqueConstraint("automation_id", "source_event_id", name="uq_pending_fires_source"),
        Index("ix_pending_fires_due", "fire_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    automation_id: Mapped[UUID] = mapped_column(
        ForeignKey("automations.automations.id", ondelete="CASCADE"), nullable=False
    )
    source_event_id: Mapped[UUID] = mapped_column(nullable=False)
    fire_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    fired: Mapped[bool] = mapped_column(nullable=False, default=False)


class DedupWindow(AutomationsBase):
    __tablename__ = "dedup_windows"

    automation_id: Mapped[UUID] = mapped_column(
        ForeignKey("automations.automations.id", ondelete="CASCADE"), primary_key=True
    )
    dedup_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
