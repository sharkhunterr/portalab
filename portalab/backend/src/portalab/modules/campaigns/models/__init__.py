"""Schema ``campaigns`` (specs/014 data-model). ``versions`` and ``activation_log`` are append-only; the log
holds closed ``[opened, closed)`` intervals and an exclusion constraint forbids overlaps per campaign;
``open_intervals`` holds the single open interval. Users are referenced by id (FK in the migration only)."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSTZRANGE, ExcludeConstraint, Range
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal


class CampaignsBase(DeclarativeBase):
    metadata = schema_metadata("campaigns")


class Campaign(CampaignsBase):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint(
            "state IN ('draft', 'scheduled', 'active', 'paused', 'ended', 'archived')", name="state"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(10), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class CampaignVersion(CampaignsBase):
    __tablename__ = "versions"
    __table_args__ = ({"info": APPEND_ONLY_INFO},)

    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.campaigns.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    effective_from: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Occurrence(CampaignsBase):
    __tablename__ = "occurrences"
    __table_args__ = (
        UniqueConstraint("campaign_id", "index", name="uq_occurrences_index"),
        CheckConstraint("status IN ('planned', 'active', 'ended', 'skipped', 'cancelled')", name="status"),
        CheckConstraint("end_at > start_at", name="window"),
        Index("ix_occurrences_window", "start_at", "end_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.campaigns.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)


class ActivationLog(CampaignsBase):
    __tablename__ = "activation_log"
    __table_args__ = (
        ExcludeConstraint(
            ("campaign_id", "="), ("during", "&&"), name="ex_activation_log_overlap", using="gist"
        ),
        CheckConstraint("cause IN ('schedule', 'manual')", name="cause"),
        {"info": APPEND_ONLY_INFO},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.campaigns.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    occurrence_id: Mapped[UUID | None] = mapped_column(ForeignKey("campaigns.occurrences.id"))
    during: Mapped[Range[datetime]] = mapped_column(TSTZRANGE, nullable=False)
    cause: Mapped[str] = mapped_column(String(10), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(
        String(200), info=not_personal("an administrator's justification")
    )


class OpenInterval(CampaignsBase):
    __tablename__ = "open_intervals"
    __table_args__ = (CheckConstraint("cause IN ('schedule', 'manual')", name="cause"),)

    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.campaigns.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    cause: Mapped[str] = mapped_column(String(10), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column()
    occurrence_id: Mapped[UUID | None] = mapped_column(ForeignKey("campaigns.occurrences.id"))
    reason: Mapped[str | None] = mapped_column(
        String(200), info=not_personal("an administrator's justification")
    )


class Override(CampaignsBase):
    __tablename__ = "overrides"
    __table_args__ = (
        CheckConstraint("kind IN ('activate', 'deactivate')", name="kind"),
        Index("ix_overrides_campaign", "campaign_id", "from_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("campaigns.campaigns.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    from_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    until_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    actor_user_id: Mapped[UUID | None] = mapped_column()
    reason: Mapped[str] = mapped_column(
        String(200), nullable=False, info=not_personal("an administrator's justification")
    )
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    expired_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class AttributeFailure(CampaignsBase):
    __tablename__ = "attribute_failures"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
