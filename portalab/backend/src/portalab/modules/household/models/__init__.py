"""Household schema ``household`` (spec 032): who belongs to which household — its master and its profiles,
each a member of its own (their accounts are identity's: the foreign keys to ``identity.users`` are the
migration's, deleting with the account) — and the profiles' access requests."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal, pii

KINDS: tuple[str, ...] = ("owner", "standard", "child", "custom")
ACCESS_STATUSES: tuple[str, ...] = ("pending", "approved", "denied")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class HouseholdBase(DeclarativeBase):
    metadata = schema_metadata("household")


class HouseholdMember(HouseholdBase):
    """A member of a household — its master (``owner_id == user_id``, kind ``owner``) or one of its profiles;
    the PIN kept as an Argon2 hash (by identity), the restrictions as the master set them."""

    __tablename__ = "members"
    __table_args__ = (
        CheckConstraint(_in("kind", KINDS), name="kind"),
        CheckConstraint("(kind = 'owner') = (owner_id = user_id)", name="owner"),
        Index("ix_members_owner_id", "owner_id", "position"),
    )

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    color: Mapped[str] = mapped_column(
        String(16), nullable=False, info=not_personal("a display colour picked from the portal's palette")
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pin_hash: Mapped[str | None] = mapped_column(String(512), info=not_personal("Argon2 hash of a PIN"))
    community_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    restrictions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, info=not_personal("the master's content settings for a profile")
    )
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    # issue 432: what its master gave for a while — minutes more on one day, no limits until a moment
    bonus_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_day: Mapped[date | None] = mapped_column(Date)
    free_until: Mapped[datetime | None] = mapped_column(TZDateTime)


class AccessRequest(HouseholdBase):
    """A profile asks its master for one object its restrictions lock (a film above its age); approved for
    good or until ``expires_at``, or refused."""

    __tablename__ = "access_requests"
    __table_args__ = (
        CheckConstraint(_in("status", ACCESS_STATUSES), name="status"),
        Index(
            "uq_access_requests_pending",
            "profile_id",
            "kind",
            "subject_ref",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_access_requests_owner_id", "owner_id", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    profile_id: Mapped[UUID] = mapped_column(nullable=False)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False, info=pii("activity", tombstone=""))
    rating: Mapped[str | None] = mapped_column(String(32), info=not_personal("the title's age rating"))
    note: Mapped[str | None] = mapped_column(String(300), info=pii("activity"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(TZDateTime)
