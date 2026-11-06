"""Schema ``requests`` (issue 363): the titles members ask the administrators for — what they told of it (its
kind, title, creators, edition, every identifier known), where it stands and why — and the members who want
it: the one who asked first, then each « me too »."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id

OPEN = ("new", "accepted", "in_progress")
STATUSES = (*OPEN, "available", "refused", "cancelled")


class RequestsBase(DeclarativeBase):
    metadata = schema_metadata("requests")


class TitleRequest(RequestsBase):
    """A title asked for. ``requester_id``: who stands for it now — the one who asked, or after they withdrew
    the member who said « me too » first. ``object_id``: the library's title once it is there."""

    __tablename__ = "requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'accepted', 'in_progress', 'available', 'refused', 'cancelled')",
            name="ck_requests_status",
        ),
        Index("ix_requests_status_updated", "status", "updated_at"),
        Index(
            "ix_requests_open_title",
            "kind",
            "folded",
            postgresql_where=text("status IN ('new', 'accepted', 'in_progress')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    folded: Mapped[str] = mapped_column(String(300), nullable=False)  # the title as two requests compare it
    creators: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    year: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)  # edition, format…
    ids: Mapped[dict[str, list[str]]] = mapped_column(JSONB, nullable=False, default=dict)
    note: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="new")
    reason: Mapped[str | None] = mapped_column(String(500))  # why it was refused
    requester_id: Mapped[UUID | None] = mapped_column()  # FK identity.users (DB), SET NULL
    object_id: Mapped[UUID | None] = mapped_column()  # the library's title (media.objects), once there
    spend_id: Mapped[UUID | None] = mapped_column()  # the Coins it cost (economy), given back if refused
    decided_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Supporter(RequestsBase):
    """A member who wants the title: ``asked`` the one who asked for it, the others said « me too »."""

    __tablename__ = "supporters"
    __table_args__ = (Index("ix_supporters_user", "user_id", "since"),)

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("requests.requests.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(primary_key=True)  # FK identity.users (DB), CASCADE
    asked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    since: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
