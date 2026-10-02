"""Identity schema ``identity`` (specs/002-identity-users/data-model.md).

Personal-data columns are classified in the kernel privacy registry; the tombstone keeps ``users.id`` and
``state='deleted'`` and nulls every classified column. Credentials and token hashes are secrets: they are
never classified as exportable data and are deleted (not scrubbed) at final deletion.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal, pii

STATES: tuple[str, ...] = (
    "pending_verification",
    "active",
    "inactive",
    "suspended",
    "pending_deletion",
    "deleted",
)
VISIBILITY_PREFERENCES: tuple[str, ...] = ("public", "community", "leaderboard", "private")
ONBOARDING_STEPS: tuple[str, ...] = (
    "profile",
    "interests",
    "notifications",
    "privacy",
    "dashboard",
    "discovery",
)
REVOKE_REASONS: tuple[str, ...] = ("logout", "suspended", "deleted", "admin", "password_change", "rotated")
EXPORT_STATUSES: tuple[str, ...] = ("queued", "ready", "failed", "expired")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


USERS_FK = "identity.users.id"


class IdentityBase(DeclarativeBase):
    metadata = schema_metadata("identity")


class User(IdentityBase):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_in("state", STATES), name="state"),
        CheckConstraint(
            f"state_before_deletion IS NULL OR {_in('state_before_deletion', STATES)}", name="prior"
        ),
        Index("uq_users_login", "login", unique=True, postgresql_where=text("login IS NOT NULL")),
        Index(
            "uq_users_display_name_key",
            "display_name_key",
            unique=True,
            postgresql_where=text("display_name_key IS NOT NULL"),
        ),
        Index("ix_users_state_state_changed_at", "state", "state_changed_at"),
        Index(
            "ix_users_deletion_due_at",
            "deletion_due_at",
            postgresql_where=text("state = 'pending_deletion'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    login: Mapped[str | None] = mapped_column(String(64), info=pii("identifier"))
    login_display: Mapped[str | None] = mapped_column(String(64), info=pii("identifier"))
    display_name: Mapped[str | None] = mapped_column(String(64), info=pii("profile"))
    display_name_key: Mapped[str | None] = mapped_column(String(128), info=pii("profile"))
    email: Mapped[str | None] = mapped_column(String(320), info=pii("contact"))
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    state_before_deletion: Mapped[str | None] = mapped_column(String(32))
    transition_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state_changed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    last_sign_in_at: Mapped[datetime | None] = mapped_column(TZDateTime, info=pii("activity"))
    deletion_requested_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    deletion_due_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Credential(IdentityBase):
    __tablename__ = "credentials"

    user_id: Mapped[UUID] = mapped_column(ForeignKey(USERS_FK, ondelete="CASCADE"), primary_key=True)
    scheme: Mapped[str] = mapped_column(String(16), nullable=False)
    hash: Mapped[str] = mapped_column(String(512), nullable=False)
    params_version: Mapped[str] = mapped_column(String(64), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class UserSession(IdentityBase):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(f"revoke_reason IS NULL OR {_in('revoke_reason', REVOKE_REASONS)}", name="reason"),
        Index("ix_sessions_user_id_active", "user_id", postgresql_where=text("revoked_at IS NULL")),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, info=not_personal("SHA-256 of an opaque session token")
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey(USERS_FK, ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    revoke_reason: Mapped[str | None] = mapped_column(String(32))
    user_agent_summary: Mapped[str | None] = mapped_column(String(128), info=pii("technical"))
    ip_prefix: Mapped[str | None] = mapped_column(String(64), info=pii("technical"))


class LoginThrottle(IdentityBase):
    __tablename__ = "login_throttle"

    key_hash: Mapped[str] = mapped_column(
        String(64), primary_key=True, info=not_personal("SHA-256 of identifier+ip prefix; no raw value")
    )
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_start: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(TZDateTime)


class VerificationToken(IdentityBase):
    __tablename__ = "verification_tokens"
    __table_args__ = (CheckConstraint("purpose IN ('verify')", name="purpose"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(USERS_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, info=not_personal("SHA-256 of a one-time token")
    )
    purpose: Mapped[str] = mapped_column(String(16), nullable=False, default="verify")
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class Profile(IdentityBase):
    __tablename__ = "profiles"

    user_id: Mapped[UUID] = mapped_column(ForeignKey(USERS_FK, ondelete="CASCADE"), primary_key=True)
    avatar_blob_key: Mapped[str | None] = mapped_column(String(128), info=pii("profile"), index=True)
    avatar_content_type: Mapped[str | None] = mapped_column(
        String(32), info=not_personal("media type of the stored image")
    )
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class ProfileField(IdentityBase):
    """Only the user's visibility *preference* is stored; effective visibility belongs to Privacy (021)."""

    __tablename__ = "profile_fields"
    __table_args__ = (
        CheckConstraint(_in("visibility_preference", VISIBILITY_PREFERENCES), name="visibility"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey(USERS_FK, ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, info=pii("profile"))
    visibility_preference: Mapped[str] = mapped_column(String(16), nullable=False, default="private")
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class AccountStateHistory(IdentityBase):
    """Append-only user history (trigger-enforced); never public by default."""

    __tablename__ = "account_state_history"
    __table_args__ = (
        Index("ix_account_state_history_user_id_seq", "user_id", "transition_seq", unique=True),
        {"info": APPEND_ONLY_INFO},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(USERS_FK), nullable=False)
    transition_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column()
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class DeletionRequest(IdentityBase):
    __tablename__ = "deletion_requests"
    __table_args__ = (
        Index(
            "uq_deletion_requests_open",
            "user_id",
            unique=True,
            postgresql_where=text("cancelled_at IS NULL AND finalized_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(USERS_FK), nullable=False)
    requested_by: Mapped[UUID | None] = mapped_column()
    requested_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    due_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    prior_state: Mapped[str] = mapped_column(String(32), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    cancelled_by: Mapped[UUID | None] = mapped_column()
    finalized_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    saga_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class OnboardingProgress(IdentityBase):
    __tablename__ = "onboarding_progress"
    __table_args__ = (CheckConstraint(_in("step", ONBOARDING_STEPS), name="step"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey(USERS_FK, ondelete="CASCADE"), primary_key=True)
    step: Mapped[str] = mapped_column(String(16), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class ExportJob(IdentityBase):
    __tablename__ = "export_jobs"
    __table_args__ = (CheckConstraint(_in("status", EXPORT_STATUSES), name="status"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(USERS_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    requested_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    blob_key: Mapped[str | None] = mapped_column(String(128))
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(TZDateTime)
