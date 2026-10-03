"""Schema ``marketplace`` (specs/015 data-model, slice A): community projects, their append-only state
history, fundings (Coins *reserved* in the 013 ledger — references only) and public notes. Users are
referenced by id (FK in the migration only)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal

STATES = (
    "'idea', 'proposal', 'open', 'validation', 'development', 'beta', 'released', 'rejected', 'abandoned'"
)


class MarketplaceBase(DeclarativeBase):
    metadata = schema_metadata("marketplace")


class Project(MarketplaceBase):
    __tablename__ = "projects"
    __table_args__ = (CheckConstraint(f"state IN ({STATES})", name="state"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    proposal_ref: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    proposer_id: Mapped[UUID | None] = mapped_column()
    title: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("a project title"))
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    funding_rules: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    rules_frozen_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    goal_amount: Mapped[int | None] = mapped_column(BigInteger)
    validated_by: Mapped[UUID | None] = mapped_column()
    validated_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ProjectStateHistory(MarketplaceBase):
    __tablename__ = "project_state_history"
    __table_args__ = ({"info": APPEND_ONLY_INFO},)

    project_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace.projects.id"), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_state: Mapped[str | None] = mapped_column(String(12))
    to_state: Mapped[str] = mapped_column(String(12), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(
        String(500), info=not_personal("an administrator's public reason for a project decision")
    )
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ProjectFunding(MarketplaceBase):
    __tablename__ = "project_fundings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('reserved', 'released', 'consumed', 'partially_consumed', 'destroyed_on_deletion')",
            name="status",
        ),
        CheckConstraint("amount > 0", name="amount"),
        Index("ix_project_fundings_project_status", "project_id", "status"),
        Index("ix_project_fundings_user", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace.projects.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    # one reservation per consumption tranche: [{"reservation": id, "amount": n, "consume_at": state,
    #   "status": reserved|released|consumed}]
    tranches: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class ProjectNote(MarketplaceBase):
    __tablename__ = "project_notes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace.projects.id"), nullable=False)
    author_id: Mapped[UUID | None] = mapped_column()
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    public_note: Mapped[str] = mapped_column(Text, nullable=False, info=not_personal("a public project note"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
