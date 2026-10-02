"""Schemas ``authz`` and ``audit`` (specs/003-roles-permissions/data-model.md).

Grants are held by roles, groups or — for allow-listed entitlement permissions only (F15) — individual users.
The Admin role is "all enabled permissions minus explicit denies": no rows are copied to it. At most one
active Admin assignment exists (partial unique index on a constant) and ``admin_singleton`` is the lock
target of the atomic transfer. ``audit.audit_entries`` is append-only (trigger) and is completed by the
Audit/Security step.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal

ADMIN_ROLE_ID = UUID("01900000-0000-7000-8000-00000000ad01")
"""Fixed id of the seeded ``admin`` role (referenced by the single-Admin partial index)."""

BASE_ROLE_IDS: dict[str, UUID] = {
    "user": UUID("01900000-0000-7000-8000-000000000001"),
    "support": UUID("01900000-0000-7000-8000-000000000002"),
    "moderator": UUID("01900000-0000-7000-8000-000000000003"),
    "editor": UUID("01900000-0000-7000-8000-000000000004"),
    "admin": ADMIN_ROLE_ID,
}
HOLDER_KINDS: tuple[str, ...] = ("role", "group", "user")
EFFECTS: tuple[str, ...] = ("allow", "deny")
SCOPE_KINDS: tuple[str, ...] = ("global", "self", "owned", "module", "service", "plugin")

# References to ``identity.users(id)`` are enforced by foreign keys created in the migrations only: the
# identity tables live in another module's MetaData, which the authz models must not import.


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class AuthzBase(DeclarativeBase):
    metadata = schema_metadata("authz")


class AuditBase(DeclarativeBase):
    metadata = schema_metadata("audit")


class Permission(AuthzBase):
    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    declared_by: Mapped[str] = mapped_column(String(128), nullable=False)
    sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reserved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_grantable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Role(AuthzBase):
    __tablename__ = "roles"
    __table_args__ = (CheckConstraint("kind IN ('base', 'custom')", name="kind"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, info=not_personal("role label"))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Group(AuthzBase):
    __tablename__ = "groups"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, info=not_personal("group label"))
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")


class Grant(AuthzBase):
    __tablename__ = "grants"
    __table_args__ = (
        CheckConstraint(_in("holder_kind", HOLDER_KINDS), name="holder_kind"),
        CheckConstraint(_in("effect", EFFECTS), name="effect"),
        CheckConstraint(_in("scope_kind", SCOPE_KINDS), name="scope_kind"),
        UniqueConstraint(
            "holder_kind",
            "holder_id",
            "permission_key",
            "scope_kind",
            "scope_ref",
            name="uq_grants_holder_scope",
        ),
        Index("ix_grants_holder", "holder_kind", "holder_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    holder_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    holder_id: Mapped[UUID] = mapped_column(nullable=False)
    permission_key: Mapped[str] = mapped_column(ForeignKey("authz.permissions.key"), nullable=False)
    effect: Mapped[str] = mapped_column(String(8), nullable=False, default="allow")
    scope_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="global")
    scope_ref: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="admin")
    created_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class UserRole(AuthzBase):
    __tablename__ = "user_roles"
    __table_args__ = (
        Index(
            "uq_user_roles_active",
            "user_id",
            "role_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "uq_user_roles_single_admin",
            text("(true)"),
            unique=True,
            postgresql_where=text(f"role_id = '{ADMIN_ROLE_ID}' AND revoked_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)  # FK identity.users (DB)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("authz.roles.id"), nullable=False)
    granted_by: Mapped[UUID | None] = mapped_column()
    granted_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class UserGroup(AuthzBase):
    __tablename__ = "user_groups"
    __table_args__ = (
        Index(
            "uq_user_groups_active",
            "user_id",
            "group_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)  # FK identity.users (DB)
    group_id: Mapped[UUID] = mapped_column(ForeignKey("authz.groups.id"), nullable=False)
    granted_by: Mapped[UUID | None] = mapped_column()
    granted_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class AdminSingleton(AuthzBase):
    __tablename__ = "admin_singleton"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    current_admin_user_id: Mapped[UUID | None] = mapped_column()  # FK identity.users (DB)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Confirmation(AuthzBase):
    __tablename__ = "confirmations"

    token_hash: Mapped[str] = mapped_column(
        String(64), primary_key=True, info=not_personal("SHA-256 of a one-time confirmation token")
    )
    principal_user_id: Mapped[UUID] = mapped_column(nullable=False)
    permission_key: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class AuditEntry(AuditBase):
    """Append-only (trigger), range-partitioned by month on ``occurred_at`` (spec 021 T018).

    ``actor_user_id`` keeps the pseudonymous id so tombstoning keeps integrity; ``seq`` orders entries and
    drives the hash-chain checkpoints.
    """

    __tablename__ = "audit_entries"
    __table_args__ = (
        CheckConstraint("decision IN ('allow', 'deny', 'n/a')", name="decision"),
        CheckConstraint("result IN ('success', 'failure', 'n/a')", name="result"),
        CheckConstraint(
            "actor_kind IN ('user', 'system', 'ai', 'automation', 'plugin', 'anonymous')", name="actor_kind"
        ),
        Index("ix_audit_entries_occurred_at", "occurred_at"),
        Index("ix_audit_entries_actor_user_id", "actor_user_id"),
        Index("ix_audit_entries_seq", "seq"),
        {"info": APPEND_ONLY_INFO, "postgresql_partition_by": "RANGE (occurred_at)"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column()
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    acting_for: Mapped[UUID | None] = mapped_column()
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(128))
    scope: Mapped[str | None] = mapped_column(String(128))
    decision: Mapped[str] = mapped_column(String(8), nullable=False)
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    correlation_id: Mapped[str | None] = mapped_column(String(64))


class AuditCheckpoint(AuditBase):
    """Append-only hash chain over ``seq`` batches of audit entries (spec 021 R7)."""

    __tablename__ = "audit_checkpoints"
    __table_args__ = ({"info": APPEND_ONLY_INFO},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    from_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    to_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    batch_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_checkpoint_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
