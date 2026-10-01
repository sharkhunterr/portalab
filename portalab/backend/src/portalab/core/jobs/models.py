"""``core.job`` — durable background job / transactional outbox row (data-model.md §2)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from portalab.core.db import CoreBase, TZDateTime

JOB_STATUSES = ("queued", "running", "succeeded", "failed", "dead")


class Job(CoreBase):
    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','dead')",
            name="status_valid",
        ),
        CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="attempts_valid"),
        Index(
            "ix_job_claimable",
            "queue",
            "run_at",
            postgresql_where=text("status = 'queued'"),
        ),
        Index(
            "ix_job_running_locks",
            "queue",
            "locked_until",
            postgresql_where=text("status = 'running'"),
        ),
        Index(
            "uq_job_queue_dedup_key",
            "queue",
            "dedup_key",
            unique=True,
            postgresql_where=text("dedup_key IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    queue: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    dedup_key: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    run_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    locked_by: Mapped[str | None] = mapped_column(String(128))
    locked_until: Mapped[datetime | None] = mapped_column(TZDateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
