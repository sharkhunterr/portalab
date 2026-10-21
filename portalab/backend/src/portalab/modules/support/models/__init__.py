"""Schema ``support`` — Slice A: incidents (specs/016-support/data-model.md). Service ids are opaque refs
(no cross-module FK); the update timeline is append-only (trigger); evidence holds pointers only (no
payload). Staff authors are referenced by their pseudonymous user id (kept after erasure)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal, pii


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
    # also shown as a banner across the portal while it is open (like a maintenance's)
    banner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


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


# --- Slice B: tickets, feedback, diagnosis ---------------------------------------------------------------
class TicketType(SupportBase):
    __tablename__ = "ticket_types"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False, info=not_personal("type label"))
    workflow_key: Mapped[str] = mapped_column(String(60), nullable=False)
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Workflow(SupportBase):
    """Versioned, append-only workflow definitions (tickets pin the version they started with)."""

    __tablename__ = "workflows"
    __table_args__ = ({"info": APPEND_ONLY_INFO},)

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Ticket(SupportBase):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="priority"),
        CheckConstraint(
            "source IN ('manual', 'ai_diagnosis', 'feedback_conversion', 'automation')", name="source"
        ),
        Index("ix_tickets_requester", "requester_id", "created_at"),
        Index("ix_tickets_queue", "state", "updated_at"),
        Index("ix_tickets_incident", "incident_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    type_key: Mapped[str] = mapped_column(String(60), nullable=False)
    workflow_key: Mapped[str] = mapped_column(String(60), nullable=False)
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=pii("content", tombstone="—"))
    description: Mapped[str] = mapped_column(Text, nullable=False, info=pii("content", tombstone=""))
    requester_id: Mapped[UUID | None] = mapped_column()  # FK identity.users (migration), SET NULL on erasure
    assignee_id: Mapped[UUID | None] = mapped_column()  # FK identity.users (migration), SET NULL
    priority: Mapped[str] = mapped_column(String(8), nullable=False)
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, info=pii("content", tombstone={}))
    service_id: Mapped[str | None] = mapped_column(String(64))
    incident_id: Mapped[UUID | None] = mapped_column(ForeignKey("support.incidents.id"))
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    feedback_id: Mapped[UUID | None] = mapped_column(ForeignKey("support.feedback_items.id"))
    technical_context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class TicketTag(SupportBase):
    __tablename__ = "ticket_tags"
    __table_args__ = (Index("ix_ticket_tags_tag", "tag"),)

    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("support.tickets.id"), primary_key=True)
    tag: Mapped[str] = mapped_column(String(60), primary_key=True)


class TicketComment(SupportBase):
    __tablename__ = "ticket_comments"
    __table_args__ = (Index("ix_ticket_comments_ticket", "ticket_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("support.tickets.id"), nullable=False)
    author_id: Mapped[UUID | None] = mapped_column()  # FK identity.users (migration), SET NULL
    body: Mapped[str] = mapped_column(Text, nullable=False, info=pii("content", tombstone=""))
    internal: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class TicketHistory(SupportBase):
    """Append-only (only an erased actor may be tombstoned)."""

    __tablename__ = "ticket_history"
    __table_args__ = (
        UniqueConstraint("ticket_id", "seq", name="uq_ticket_history_seq"),
        CheckConstraint(
            "kind IN ('created', 'transition', 'assignment', 'field_changed', 'tag', 'incident_linked',"
            " 'comment_added', 'attachment_added')",
            name="kind",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("support.tickets.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column()
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Attachment(SupportBase):
    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachments_ticket", "ticket_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("support.tickets.id"), nullable=False)
    comment_id: Mapped[UUID | None] = mapped_column(ForeignKey("support.ticket_comments.id"))
    uploaded_by: Mapped[UUID | None] = mapped_column()  # FK identity.users (migration), SET NULL
    blob_key: Mapped[str] = mapped_column(String(200), nullable=False)
    filename: Mapped[str] = mapped_column(String(120), nullable=False, info=pii("content", tombstone="file"))
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class TicketDraft(SupportBase):
    __tablename__ = "ticket_drafts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)  # FK identity.users (migration), CASCADE
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, info=pii("content", tombstone={}))
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    diagnosis_run_id: Mapped[UUID | None] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class DiagnosisRun(SupportBase):
    __tablename__ = "diagnosis_runs"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('running', 'resolved', 'ticket_prefilled', 'inconclusive', 'failed')", name="outcome"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)  # FK identity.users (migration), CASCADE
    steps: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, info=pii("content", tombstone=[])
    )
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class FeedbackForm(SupportBase):
    __tablename__ = "feedback_forms"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False, info=not_personal("form label"))
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    # 027: a form may be requested from members between two dates (one answer each)
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default="", info=not_personal("form description")
    )
    icon: Mapped[str | None] = mapped_column(String(40))
    requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    opens_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    closes_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class FeedbackItem(SupportBase):
    __tablename__ = "feedback_items"
    __table_args__ = (
        CheckConstraint("status IN ('new', 'reviewed', 'converted', 'dismissed')", name="status"),
        Index("ix_feedback_items_status", "status", "created_at"),
        Index("ix_feedback_items_form_submitter", "form_key", "submitter_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    form_key: Mapped[str] = mapped_column(String(60), nullable=False)
    form_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    submitter_id: Mapped[UUID | None] = mapped_column()  # FK identity.users (migration), SET NULL
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, info=pii("content", tombstone={}))
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    reviewed_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    # 027: staff may answer the member (shown in their feedback list)
    reply: Mapped[str | None] = mapped_column(Text, info=pii("content"))
    replied_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class FeedbackConversion(SupportBase):
    """Append-only provenance of a conversion (one per feedback and target kind)."""

    __tablename__ = "feedback_conversions"
    __table_args__ = (
        UniqueConstraint("feedback_id", "target_kind", name="uq_feedback_conversions_target"),
        CheckConstraint(
            "target_kind IN ('ticket', 'contribution', 'feature_proposal', 'community_project')",
            name="target_kind",
        ),
        {"info": APPEND_ONLY_INFO},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    feedback_id: Mapped[UUID] = mapped_column(ForeignKey("support.feedback_items.id"), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    target_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    converted_by: Mapped[UUID | None] = mapped_column()
    converted_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
