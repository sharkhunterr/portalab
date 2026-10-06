"""Schema ``notify`` (specs/010-notifications/data-model.md). Communications are immutable facts; the
notification center holds one rendered row per recipient (personal data, ``activity``); deliveries are per
recipient and channel; e-mail bodies are dropped once sent."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal, pii


class NotifyBase(DeclarativeBase):
    metadata = schema_metadata("notify")


class Category(NotifyBase):
    __tablename__ = "categories"

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    owner: Mapped[str] = mapped_column(String(80), nullable=False)
    label_key: Mapped[str] = mapped_column(String(128), nullable=False)
    default_priority: Mapped[str] = mapped_column(String(10), nullable=False)
    default_channels: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    mandatory_channels: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    user_mutable: Mapped[bool] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Communication(NotifyBase):
    __tablename__ = "communications"
    __table_args__ = (
        UniqueConstraint("source", "dedup_key", name="uq_communications_source_dedup"),
        CheckConstraint("kind IN ('notification', 'alert')", name="kind"),
        CheckConstraint("priority IN ('low', 'normal', 'high', 'critical')", name="priority"),
        CheckConstraint("kind = 'notification' OR priority IN ('high', 'critical')", name="alert_priority"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(96), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(160))
    dedup_key: Mapped[str] = mapped_column(String(200), nullable=False)
    template_key: Mapped[str] = mapped_column(String(128), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    subject_ref: Mapped[str | None] = mapped_column(String(160))
    audience_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    required_permission: Mapped[str | None] = mapped_column(String(128))
    produced_by: Mapped[str] = mapped_column(String(80), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(TZDateTime)
    action_url: Mapped[str | None] = mapped_column(String(256))
    # 027: a newsletter's own e-mail ({subject, text, html}); dropped with the communication's retention
    email_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, info=not_personal("newsletter content"))
    recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Notification(NotifyBase):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_inbox", "user_id", "archived_at", "created_at"),
        CheckConstraint("kind IN ('notification', 'alert')", name="kind"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    communication_id: Mapped[UUID] = mapped_column(ForeignKey("notify.communications.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    language: Mapped[str] = mapped_column(String(35), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, info=pii("activity", tombstone=""))
    body: Mapped[str] = mapped_column(Text, nullable=False, info=pii("activity", tombstone=""))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(96), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_ref: Mapped[str | None] = mapped_column(String(160))
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    action_url: Mapped[str | None] = mapped_column(String(256))
    read_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    archived_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Delivery(NotifyBase):
    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint("communication_id", "user_id", "channel", name="uq_deliveries_recipient_channel"),
        CheckConstraint("status IN ('pending', 'sent', 'delivered', 'failed', 'suppressed')", name="status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    communication_id: Mapped[UUID] = mapped_column(ForeignKey("notify.communications.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    suppress_reason: Mapped[str | None] = mapped_column(String(20))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class EmailOutbox(NotifyBase):
    __tablename__ = "email_outbox"

    delivery_id: Mapped[UUID] = mapped_column(
        ForeignKey("notify.deliveries.id", ondelete="CASCADE"), primary_key=True
    )
    to_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, info=not_personal("salted hash, never the address")
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False, info=pii("activity", tombstone=""))
    body_text: Mapped[str] = mapped_column(Text, nullable=False, info=pii("activity", tombstone=""))
    body_html: Mapped[str | None] = mapped_column(Text, info=pii("activity"))
    next_attempt_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MaintenanceReminder(NotifyBase):
    __tablename__ = "maintenance_reminders"
    __table_args__ = (
        UniqueConstraint("maintenance_id", "schedule_version", "kind", name="uq_maintenance_reminders"),
        CheckConstraint("kind IN ('j1', 'h1', 'start', 'corrective')", name="kind"),
        CheckConstraint("status IN ('scheduled', 'sent', 'cancelled', 'expired')", name="status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    maintenance_id: Mapped[str] = mapped_column(String(64), nullable=False)
    schedule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    service_id: Mapped[str | None] = mapped_column(String(64))
    run_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    valid_until: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    communication_id: Mapped[UUID | None] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class DigestState(NotifyBase):
    __tablename__ = "digest_state"

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    last_digest_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
