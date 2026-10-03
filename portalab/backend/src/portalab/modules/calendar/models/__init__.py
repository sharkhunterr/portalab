"""Schema ``calendar``: only opt-in reminders (items stay with their owners)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id


class CalendarBase(DeclarativeBase):
    metadata = schema_metadata("calendar")


class Reminder(CalendarBase):
    __tablename__ = "reminders"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "source_kind", "source_id", "lead_minutes", name="uq_reminders_item_lead"
        ),
        CheckConstraint("status IN ('scheduled', 'sent', 'cancelled', 'stale')", name="status"),
        Index("ix_reminders_user", "user_id", "remind_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)  # FK identity.users (migration), CASCADE
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    lead_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    remind_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    last_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
