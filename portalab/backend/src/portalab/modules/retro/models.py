"""Retro schema ``retro`` (issue 419): the sittings — a member (or a household profile) playing a library's
game in the portal: since when, until when, the minutes the page counted while the game ran, and whether the
library was told (its play time). The foreign key to ``identity.users`` is the migration's (the sittings go
with the account)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Float, Index, Integer, LargeBinary, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
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


class GameSave(RetroBase):
    """420: a member's progress in a game — its own save (``sram``: the battery memory, one per game) or a
    save state (``state``, in a slot; slot 0 is where the game was left) — kept in the portal per member and
    per household profile, copied to the library (``remote_id``) once ``synced_at`` catches ``updated_at``."""

    __tablename__ = "saves"
    __table_args__ = (
        UniqueConstraint("user_id", "service_id", "external_id", "kind", "slot", name="uq_saves_slot"),
        CheckConstraint("kind IN ('sram', 'state')", name="kind"),
        Index("ix_saves_user_object", "user_id", "object_id"),
        Index("ix_saves_unsynced", "updated_at", postgresql_where=text("synced_at IS NULL")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    object_id: Mapped[UUID] = mapped_column(nullable=False)
    service_id: Mapped[UUID] = mapped_column(nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    core: Mapped[str] = mapped_column(String(64), nullable=False, info=not_personal("an emulator's name"))
    data: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, info=not_personal("an emulator's memory of a game"), deferred=True
    )
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    screenshot: Mapped[bytes | None] = mapped_column(
        LargeBinary, info=not_personal("a picture of the game's screen"), deferred=True
    )
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    remote_id: Mapped[str | None] = mapped_column(String(64))  # its copy in the library
    synced_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class Preference(RetroBase):
    """421: a member's emulator settings for one core — its controls (keyboard and gamepad mapping), its
    options — kept by the portal so they follow the member from one device to another."""

    __tablename__ = "preferences"

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    core: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, info=not_personal("an emulator's controls and options")
    )
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
