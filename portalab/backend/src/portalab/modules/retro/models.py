"""Retro schema ``retro`` (issue 419): the sittings — a member (or a household profile) playing a library's
game in the portal: since when, until when, the minutes the page counted while the game ran, and whether the
library was told (its play time). The foreign key to ``identity.users`` is the migration's (the sittings go
with the account)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Float, Index, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal, pii


class RetroBase(DeclarativeBase):
    metadata = schema_metadata("retro")


class Sitting(RetroBase):
    __tablename__ = "sittings"
    __table_args__ = (
        Index("ix_sittings_user_id", "user_id", "started_at"),
        Index("ix_sittings_open", "last_seen_at", postgresql_where=text("ended_at IS NULL")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    object_id: Mapped[UUID] = mapped_column(nullable=False)
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    platform_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(500), nullable=False, info=pii("activity", tombstone=""))
    platform: Mapped[str] = mapped_column(String(64), nullable=False, info=not_personal("a console's name"))
    core: Mapped[str] = mapped_column(String(64), nullable=False, info=not_personal("an emulator's name"))
    started_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    played_s: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    told_at: Mapped[datetime | None] = mapped_column(TZDateTime)  # the library told of it
