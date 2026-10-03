"""Schema ``support`` — Slice A: incidents (specs/016-support/data-model.md). Service ids are opaque refs
(no cross-module FK); the update timeline is append-only (trigger); evidence holds pointers only (no
payload). Staff authors are referenced by their pseudonymous user id (kept after erasure)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal


class SupportBase(DeclarativeBase):
    metadata = schema_metadata("support")


class Incident(SupportBase):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("source", "dedup_key", name="uq_incidents_source_dedup"),
        UniqueConstraint("number", name="uq_incidents_number"),
        CheckConstraint("severity IN ('minor', 'major', 'critical')", name="severity"),
        CheckConstraint("state IN ('investigating', 'identified', 'monitoring', 'resolved')", name="state"),
        CheckConstraint("source IN ('manual', 'observability', 'health', 'automation')", name="source"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("incident title"))
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    dedup_key: Mapped[str | None] = mapped_column(String(160))
    created_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class IncidentServiceLink(SupportBase):
    __tablename__ = "incident_services"

    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("support.incidents.id", ondelete="CASCADE"), primary_key=True
    )
    service_id: Mapped[str] = mapped_column(String(64), primary_key=True)


class IncidentUpdate(SupportBase):
    __tablename__ = "incident_updates"
    __table_args__ = (
        UniqueConstraint("incident_id", "update_seq", name="uq_incident_updates_seq"),
        CheckConstraint("state IN ('investigating', 'identified', 'monitoring', 'resolved')", name="state"),
        {"info": APPEND_ONLY_INFO},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("support.incidents.id"), nullable=False)
    update_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    author_user_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class IncidentEvidence(SupportBase):
    __tablename__ = "incident_evidence"

    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("support.incidents.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_ref: Mapped[str] = mapped_column(String(200), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
