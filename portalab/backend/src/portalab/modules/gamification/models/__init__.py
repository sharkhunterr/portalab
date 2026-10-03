"""Schema ``gamification`` (specs/013 data-model). ``transactions`` is the append-only ledger of the three
values (triggers forbid UPDATE/DELETE); ``balances`` is the transactional cache (amount = spendable, never
negative); definitions are append-only versions effective by instant; progress state is per user.
Columns referencing ``identity.users`` carry their foreign key in the migration only."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.append_only import APPEND_ONLY_INFO
from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal

VALUE_CHECK = "value IN ('xp', 'contribution', 'coins')"


class GamificationBase(DeclarativeBase):
    metadata = schema_metadata("gamification")


class LedgerTransaction(GamificationBase):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(VALUE_CHECK, name="value"),
        CheckConstraint(
            "kind IN ('grant', 'spend', 'refund', 'correction', 'destruction', 'manual', 'reserve', "
            "'reserve_release', 'reserve_consume')",
            name="kind",
        ),
        Index("ix_transactions_user_value", "user_id", "value", "seq"),
        Index("ix_transactions_source", "source_kind", "source_ref"),
        Index("ix_transactions_rule", "user_id", "rule_key", "occurred_at"),
        {"info": APPEND_ONLY_INFO},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    value: Mapped[str] = mapped_column(String(12), nullable=False)
    delta: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(200))
    rule_key: Mapped[str | None] = mapped_column(String(96))
    rule_version: Mapped[int | None] = mapped_column(Integer)
    trigger_event_id: Mapped[UUID | None] = mapped_column()
    idempotency_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    base_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    multiplier: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=1)
    modifiers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    guards: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    actor_user_id: Mapped[UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(
        String(200), info=not_personal("an administrator's justification, never about the user")
    )
    reverses_transaction_id: Mapped[UUID | None] = mapped_column(ForeignKey("gamification.transactions.id"))
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Balance(GamificationBase):
    __tablename__ = "balances"
    __table_args__ = (
        CheckConstraint(VALUE_CHECK, name="value"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
    )

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(String(12), primary_key=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    level: Mapped[int | None] = mapped_column(Integer)
    curve_version: Mapped[int | None] = mapped_column(Integer)


class Reservation(GamificationBase):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'released', 'consumed', 'destroyed')", name="status"),
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_reservations_user", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    reserve_tx_id: Mapped[UUID] = mapped_column(ForeignKey("gamification.transactions.id"), nullable=False)
    resolution_tx_id: Mapped[UUID | None] = mapped_column(ForeignKey("gamification.transactions.id"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class Withheld(GamificationBase):
    __tablename__ = "withheld"
    __table_args__ = (
        CheckConstraint(VALUE_CHECK, name="value"),
        CheckConstraint("reason IN ('cooldown', 'cap', 'anomaly')", name="reason"),
        CheckConstraint("status IN ('flagged', 'approved', 'rejected', 'dropped')", name="status"),
        Index("ix_withheld_status", "status", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    value: Mapped[str] = mapped_column(String(12), nullable=False)
    proposed_delta: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(10), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(200))
    rule_key: Mapped[str | None] = mapped_column(String(96))
    rule_version: Mapped[int | None] = mapped_column(Integer)
    trigger_event_id: Mapped[UUID | None] = mapped_column()
    idempotency_key: Mapped[str] = mapped_column(String(300), nullable=False)
    flag_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("gamification.anomaly_flags.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(
        String(200), info=not_personal("an administrator's review note")
    )
    reviewed_by: Mapped[UUID | None] = mapped_column()
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class AnomalyFlag(GamificationBase):
    __tablename__ = "anomaly_flags"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'dismissed', 'confirmed')", name="status"),
        Index("ix_anomaly_flags_status", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    window_start: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    reviewed_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(TZDateTime)


class RewardRule(GamificationBase):
    __tablename__ = "reward_rules"
    __table_args__ = (CheckConstraint("status IN ('draft', 'active', 'retired')", name="status"),)

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(TZDateTime)
    retired_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    created_by: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class LevelCurve(GamificationBase):
    __tablename__ = "level_curves"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    effective_from: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Achievement(GamificationBase):
    __tablename__ = "achievements"
    __table_args__ = (CheckConstraint("status IN ('active', 'retired')", name="status"),)

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class UserAchievement(GamificationBase):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_key", name="uq_user_achievements"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    achievement_key: Mapped[str] = mapped_column(String(96), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    transaction_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


class Counter(GamificationBase):
    __tablename__ = "counters"

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    counter_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class UsageWindow(GamificationBase):
    __tablename__ = "usage_windows"

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    rule_key: Mapped[str] = mapped_column(String(96), primary_key=True)
    window_kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(TZDateTime, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class AppliedEvent(GamificationBase):
    """Events already processed by the reward consumer (exactly-once counters and grants)."""

    __tablename__ = "applied_events"

    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(nullable=False)
    applied_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, index=True)


class ProgressionPreference(GamificationBase):
    """The owner's visibility level for the ``progression`` datum class (021)."""

    __tablename__ = "progression_preferences"
    __table_args__ = (
        CheckConstraint("level IN ('public', 'community', 'leaderboard', 'private')", name="level"),
    )

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    level: Mapped[str] = mapped_column(String(12), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class LeaderboardSnapshot(GamificationBase):
    """Slice B (R13): a materialized ranking per ``(metric, period)``, rebuilt by the leaderboard job.
    ``entries`` hold ``[user_id, score]`` pairs in rank order (ties: earliest attainment, then id);
    visibility is applied at read time, never baked in."""

    __tablename__ = "leaderboard_snapshots"
    __table_args__ = (CheckConstraint("period IN ('all', 'month', 'week')", name="period"),)

    metric: Mapped[str] = mapped_column(String(32), primary_key=True)
    period: Mapped[str] = mapped_column(String(8), primary_key=True)
    period_start: Mapped[datetime | None] = mapped_column(TZDateTime)
    computed_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    entries: Mapped[list[list[Any]]] = mapped_column(
        JSONB, nullable=False, default=list, info=not_personal("user ids and scores, rebuilt by the job")
    )


class Quest(GamificationBase):
    """Slice C (R11): quests, daily objectives and challenges (a challenge is a time-boxed quest, OQ-62)."""

    __tablename__ = "quests"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'retired')", name="status"),
        CheckConstraint("kind IN ('quest', 'daily', 'challenge')", name="kind"),
    )

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class QuestProgress(GamificationBase):
    """A user's progress on a quest for one period (``once``, a local day or an ISO week); completion
    happens at most once per ``(user, quest, period)``."""

    __tablename__ = "quest_progress"

    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    quest_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    period_key: Mapped[str] = mapped_column(String(16), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    counts: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
