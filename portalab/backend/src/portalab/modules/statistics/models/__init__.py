"""Schema ``stats`` (specs/017-statistics/data-model.md). Definitions are append-only versions (their
activation state lives in ``definition_status``); buckets and members are derived and rebuildable;
``applied_events`` makes the projection idempotent inside the bucket transaction (live and replay)."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Date, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import pii

COMMUNITY = UUID(int=0)  # scope_id of community rows (personal rows carry the user id)


class StatsBase(DeclarativeBase):
    metadata = schema_metadata("stats")


class Definition(StatsBase):
    __tablename__ = "definitions"
    __table_args__ = (
        CheckConstraint("change_policy IN ('forward_only', 'rebuild')", name="change_policy"),
        {"info": APPEND_ONLY_INFO},
    )

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    change_policy: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class DefinitionStatus(StatsBase):
    __tablename__ = "definition_status"
    __table_args__ = (CheckConstraint("status IN ('draft', 'active', 'retired')", name="status"),)

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    status: Mapped[str] = mapped_column(String(8), nullable=False)
    active_version: Mapped[int | None] = mapped_column(Integer)
    latest_version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Bucket(StatsBase):
    __tablename__ = "buckets"

    stat_key: Mapped[str] = mapped_column(String(96), primary_key=True)
    def_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(10), primary_key=True)
    scope_id: Mapped[UUID] = mapped_column(primary_key=True, info=pii("activity", tombstone=COMMUNITY))
    bucket_day: Mapped[date] = mapped_column(Date, primary_key=True)
    dims_hash: Mapped[str] = mapped_column(String(40), primary_key=True)
    dims: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sum: Mapped[float] = mapped_column(Numeric, nullable=False, default=0)
    min: Mapped[float | None] = mapped_column(Numeric)
    max: Mapped[float | None] = mapped_column(Numeric)


class Member(StatsBase):
    __tablename__ = "members"

    stat_key: Mapped[str] = mapped_column(String(96), primary_key=True)
    def_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(10), primary_key=True)
    scope_id: Mapped[UUID] = mapped_column(primary_key=True, info=pii("activity", tombstone=COMMUNITY))
    bucket_day: Mapped[date] = mapped_column(Date, primary_key=True)
    dims_hash: Mapped[str] = mapped_column(String(40), primary_key=True)
    member_hash: Mapped[str] = mapped_column(String(64), primary_key=True)


class AppliedEvent(StatsBase):
    __tablename__ = "applied_events"

    stat_key: Mapped[str] = mapped_column(String(96), primary_key=True)
    def_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    bucket_day: Mapped[date] = mapped_column(Date, nullable=False)


class ProjectionState(StatsBase):
    __tablename__ = "projection_state"

    stat_key: Mapped[str] = mapped_column(String(96), primary_key=True)
    def_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_event_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    events: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    start_after_seq: Mapped[int | None] = mapped_column(BigInteger)  # forward_only: fold events after this
    stop_after_seq: Mapped[int | None] = mapped_column(BigInteger)  # superseded: fold events up to this
    lineage_from: Mapped[int | None] = mapped_column(Integer)  # oldest version whose buckets make history
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Unlock(StatsBase):
    __tablename__ = "unlocks"

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    stat_key: Mapped[str] = mapped_column(String(96), primary_key=True)
    unlocked_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    reason: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, info=pii("activity", tombstone={}))


class WrappedDefinition(StatsBase):
    __tablename__ = "wrapped_definitions"
    __table_args__ = (
        CheckConstraint("period_kind IN ('month', 'quarter', 'year')", name="period_kind"),
        CheckConstraint("status IN ('draft', 'active', 'retired')", name="status"),
    )

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    period_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    stat_keys: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class WrappedSnapshot(StatsBase):
    __tablename__ = "wrapped_snapshots"
    __table_args__ = (
        CheckConstraint("subject_scope IN ('user', 'community')", name="subject_scope"),
    )  # immutable (UPDATE refused by trigger); deleted with the account

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    wrapped_key: Mapped[str] = mapped_column(String(96), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    subject_scope: Mapped[str] = mapped_column(String(10), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column()
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, info=pii("activity", tombstone={}))
    generated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class RebuildRun(StatsBase):
    __tablename__ = "rebuild_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    stat_key: Mapped[str] = mapped_column(String(96), nullable=False)
    def_version: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_by: Mapped[UUID | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TZDateTime)
