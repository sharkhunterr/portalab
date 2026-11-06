"""Schema ``requests`` (issue 363, #378): what members asked the team for — a book, an audiobook, a game… —
as they told it (its kind, title, creators, edition, every identifier known), where the team stands on
it, and the library's title once it arrived. The request itself (who asked, its state for the portal) is
the portal's (media's requests): this is the team's side, as a request service keeps its own."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id

OPEN = ("new", "accepted", "in_progress")
STATUSES = (*OPEN, "available", "refused", "cancelled")


class RequestsBase(DeclarativeBase):
    metadata = schema_metadata("requests")


class TitleRequest(RequestsBase):
    """A title asked of the team. ``object_id``: the library's title once it is there."""

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
    folded: Mapped[str] = mapped_column(String(300), nullable=False)
    creators: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    year: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)  # edition, format…
    ids: Mapped[dict[str, list[str]]] = mapped_column(JSONB, nullable=False, default=dict)
    note: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="new")
    object_id: Mapped[UUID | None] = mapped_column()  # the library's title (media.objects), once there
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
