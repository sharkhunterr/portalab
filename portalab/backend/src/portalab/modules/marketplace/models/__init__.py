"""Schema ``marketplace`` (specs/015 data-model). Slice A: community projects, their append-only state
history, fundings (Coins *reserved* in the 013 ledger — references only) and public notes. Slice B: the
catalog (categories, products, append-only versions so history is never reinterpreted), ownerships with
their price/conditions snapshot and append-only refunds. Users are referenced by id (FK in the migration
only); ledger transactions by id."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, text
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


# --- slice B: catalog ------------------------------------------------------------------------------------
class Category(MarketplaceBase):
    __tablename__ = "categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    label_key: Mapped[str] = mapped_column(String(160), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    icon: Mapped[str | None] = mapped_column(String(64))  # 027 US8: collections shown as shop shelves


class Product(MarketplaceBase):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("state IN ('draft', 'available', 'unavailable', 'archived')", name="state"),
        CheckConstraint("rarity IN ('common', 'rare', 'epic', 'legendary')", name="rarity"),
        CheckConstraint(
            "poster_effect IN ('auto', 'none', 'shine', 'glitch', 'spin', 'neon', 'blink')",
            name="poster_effect",
        ),
        Index("ix_products_state", "state", "category_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(96), nullable=False)
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("marketplace.categories.id"))
    state: Mapped[str] = mapped_column(String(12), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    repeatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extension_ref: Mapped[str | None] = mapped_column(String(120))
    # presentation (027 US8): merchandising only — never part of price, conditions or history
    rarity: Mapped[str] = mapped_column(String(12), nullable=False, default="common", server_default="common")
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    poster_effect: Mapped[str] = mapped_column(
        String(12), nullable=False, default="auto", server_default="auto"
    )
    icon: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ProductVersion(MarketplaceBase):
    __tablename__ = "product_versions"
    __table_args__ = ({"info": APPEND_ONLY_INFO},)

    product_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace.products.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    price_coins: Mapped[int | None] = mapped_column(BigInteger)
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    refund_policy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    names: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    descriptions: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    config_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_from: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    changed_by: Mapped[UUID | None] = mapped_column()


class Ownership(MarketplaceBase):
    __tablename__ = "ownerships"
    __table_args__ = (
        CheckConstraint("origin IN ('purchase', 'grant')", name="origin"),
        CheckConstraint(
            "state IN ('active', 'needs_configuration', 'activation_failed', 'revoked', 'refunded', "
            "'expired')",
            name="state",
        ),
        Index(
            "uq_ownerships_permanent",
            "user_id",
            "product_id",
            unique=True,
            postgresql_where=text("state NOT IN ('revoked', 'refunded', 'expired') AND NOT repeatable"),
        ),
        Index("ix_ownerships_user", "user_id", "acquired_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace.products.id"), nullable=False)
    origin: Mapped[str] = mapped_column(String(10), nullable=False)
    repeatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    product_version: Mapped[int] = mapped_column(Integer, nullable=False)
    price_paid: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    conditions_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    purchase_tx_ref: Mapped[UUID | None] = mapped_column()
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    activation_detail: Mapped[str | None] = mapped_column(
        String(200), info=not_personal("a technical status")
    )
    activation_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    acquired_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    revoke_ground: Mapped[str | None] = mapped_column(String(24))
    revoke_reason: Mapped[str | None] = mapped_column(
        String(500), info=not_personal("an administrator's reason")
    )


class Refund(MarketplaceBase):
    __tablename__ = "refunds"
    __table_args__ = ({"info": APPEND_ONLY_INFO},)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    ownership_id: Mapped[UUID] = mapped_column(ForeignKey("marketplace.ownerships.id"), nullable=False)
    refund_tx_ref: Mapped[UUID | None] = mapped_column()
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    percent: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False, info=not_personal("a refund reason"))
    actor_user_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
