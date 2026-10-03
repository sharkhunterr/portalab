"""gamification schema — economy ledger, rules, levels, achievements

Revision ID: gamification_0001
Revises:
Create Date: 2026-10-13 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "gamification_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("gamification",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
TABLES = (
    "withheld",
    "reservations",
    "user_achievements",
    "usage_windows",
    "transactions",
    "reward_rules",
    "progression_preferences",
    "level_curves",
    "counters",
    "balances",
    "applied_events",
    "anomaly_flags",
    "achievements",
)


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "gamification"')
    op.create_table(
        "achievements",
        sa.Column("key", sa.String(length=96), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("effective_from", TZ, nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'retired')", name="ck_achievements_status"),
        sa.PrimaryKeyConstraint("key", "version", name="pk_achievements"),
        schema="gamification",
    )
    op.create_table(
        "anomaly_flags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("window_start", TZ, nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("reviewed_at", TZ, nullable=True),
        sa.CheckConstraint("status IN ('open', 'dismissed', 'confirmed')", name="ck_anomaly_flags_status"),
        sa.PrimaryKeyConstraint("id", name="pk_anomaly_flags"),
        _user_fk("anomaly_flags", "user_id", "CASCADE"),
        schema="gamification",
    )
    op.create_index(
        "ix_anomaly_flags_status",
        "anomaly_flags",
        ["status", "created_at"],
        unique=False,
        schema="gamification",
    )
    op.create_table(
        "applied_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("applied_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("event_id", name="pk_applied_events"),
        _user_fk("applied_events", "user_id", "CASCADE"),
        schema="gamification",
    )
    op.create_index(
        op.f("ix_applied_events_applied_at"),
        "applied_events",
        ["applied_at"],
        unique=False,
        schema="gamification",
    )
    op.create_table(
        "balances",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.String(length=12), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("last_seq", sa.BigInteger(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("curve_version", sa.Integer(), nullable=True),
        sa.CheckConstraint("value IN ('xp', 'contribution', 'coins')", name="ck_balances_value"),
        sa.CheckConstraint("amount >= 0", name="ck_balances_amount_non_negative"),
        sa.PrimaryKeyConstraint("user_id", "value", name="pk_balances"),
        _user_fk("balances", "user_id", "CASCADE"),
        schema="gamification",
    )
    op.create_table(
        "counters",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("counter_key", sa.String(length=160), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("user_id", "counter_key", name="pk_counters"),
        _user_fk("counters", "user_id", "CASCADE"),
        schema="gamification",
    )
    op.create_table(
        "level_curves",
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_from", TZ, nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("version", name="pk_level_curves"),
        schema="gamification",
    )
    op.create_table(
        "progression_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(length=12), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint(
            "level IN ('public', 'community', 'leaderboard', 'private')",
            name="ck_progression_preferences_level",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_progression_preferences"),
        _user_fk("progression_preferences", "user_id", "CASCADE"),
        schema="gamification",
    )
    op.create_table(
        "reward_rules",
        sa.Column("key", sa.String(length=96), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("effective_from", TZ, nullable=True),
        sa.Column("retired_at", TZ, nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_reward_rules_status"),
        sa.PrimaryKeyConstraint("key", "version", name="pk_reward_rules"),
        schema="gamification",
    )
    op.create_index(
        op.f("ix_reward_rules_event_type"),
        "reward_rules",
        ["event_type"],
        unique=False,
        schema="gamification",
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.String(length=12), nullable=False),
        sa.Column("delta", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("source_ref", sa.String(length=200), nullable=True),
        sa.Column("rule_key", sa.String(length=96), nullable=True),
        sa.Column("rule_version", sa.Integer(), nullable=True),
        sa.Column("trigger_event_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=300), nullable=False),
        sa.Column("base_amount", sa.BigInteger(), nullable=False),
        sa.Column("multiplier", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("modifiers", postgresql.JSONB(), nullable=False),
        sa.Column("guards", postgresql.JSONB(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("reverses_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.Column("recorded_at", TZ, nullable=False),
        sa.CheckConstraint(
            "kind IN ('grant', 'spend', 'refund', 'correction', 'destruction', 'manual', 'reserve', 'reserve_release', 'reserve_consume')",
            name="ck_transactions_kind",
        ),
        sa.CheckConstraint("value IN ('xp', 'contribution', 'coins')", name="ck_transactions_value"),
        sa.ForeignKeyConstraint(
            ["reverses_transaction_id"],
            ["gamification.transactions.id"],
            name="fk_transactions_reverses_transaction_id_transactions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transactions"),
        sa.UniqueConstraint("idempotency_key", name="uq_transactions_idempotency_key"),
        sa.UniqueConstraint("seq", name="uq_transactions_seq"),
        schema="gamification",
        info={"portalab_append_only": True},
    )
    op.create_index(
        "ix_transactions_rule",
        "transactions",
        ["user_id", "rule_key", "occurred_at"],
        unique=False,
        schema="gamification",
    )
    op.create_index(
        "ix_transactions_source",
        "transactions",
        ["source_kind", "source_ref"],
        unique=False,
        schema="gamification",
    )
    op.create_index(
        "ix_transactions_user_value",
        "transactions",
        ["user_id", "value", "seq"],
        unique=False,
        schema="gamification",
    )
    op.create_table(
        "usage_windows",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rule_key", sa.String(length=96), nullable=False),
        sa.Column("window_kind", sa.String(length=8), nullable=False),
        sa.Column("window_start", TZ, nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint(
            "user_id", "rule_key", "window_kind", "window_start", name="pk_usage_windows"
        ),
        _user_fk("transactions", "user_id", "RESTRICT"),
        _user_fk("usage_windows", "user_id", "CASCADE"),
        schema="gamification",
    )
    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("achievement_key", sa.String(length=96), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("unlocked_at", TZ, nullable=False),
        sa.Column("transaction_ids", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_user_achievements"),
        sa.UniqueConstraint("user_id", "achievement_key", name="uq_user_achievements"),
        _user_fk("user_achievements", "user_id", "CASCADE"),
        schema="gamification",
    )
    op.create_table(
        "reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("source_ref", sa.String(length=200), nullable=False),
        sa.Column("idempotency_key", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("reserve_tx_id", sa.Uuid(), nullable=False),
        sa.Column("resolution_tx_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("resolved_at", TZ, nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'released', 'consumed', 'destroyed')", name="ck_reservations_status"
        ),
        sa.CheckConstraint("amount > 0", name="ck_reservations_amount_positive"),
        sa.ForeignKeyConstraint(
            ["reserve_tx_id"],
            ["gamification.transactions.id"],
            name="fk_reservations_reserve_tx_id_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["resolution_tx_id"],
            ["gamification.transactions.id"],
            name="fk_reservations_resolution_tx_id_transactions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reservations"),
        sa.UniqueConstraint("idempotency_key", name="uq_reservations_idempotency_key"),
        _user_fk("reservations", "user_id", "CASCADE"),
        schema="gamification",
    )
    op.create_index(
        "ix_reservations_user", "reservations", ["user_id", "status"], unique=False, schema="gamification"
    )
    op.create_table(
        "withheld",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.String(length=12), nullable=False),
        sa.Column("proposed_delta", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(length=10), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("source_ref", sa.String(length=200), nullable=True),
        sa.Column("rule_key", sa.String(length=96), nullable=True),
        sa.Column("rule_version", sa.Integer(), nullable=True),
        sa.Column("trigger_event_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=300), nullable=False),
        sa.Column("flag_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("decision_reason", sa.String(length=200), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.Column("reviewed_at", TZ, nullable=True),
        sa.CheckConstraint("reason IN ('cooldown', 'cap', 'anomaly')", name="ck_withheld_reason"),
        sa.CheckConstraint(
            "status IN ('flagged', 'approved', 'rejected', 'dropped')", name="ck_withheld_status"
        ),
        sa.CheckConstraint("value IN ('xp', 'contribution', 'coins')", name="ck_withheld_value"),
        sa.ForeignKeyConstraint(
            ["flag_id"],
            ["gamification.anomaly_flags.id"],
            name="fk_withheld_flag_id_anomaly_flags",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_withheld"),
        _user_fk("withheld", "user_id", "CASCADE"),
        schema="gamification",
    )
    op.create_index(
        "ix_withheld_status", "withheld", ["status", "occurred_at"], unique=False, schema="gamification"
    )
    for statement in append_only_ddl("gamification", "transactions"):
        op.execute(statement)


def downgrade() -> None:
    for statement in drop_append_only_ddl("gamification", "transactions"):
        op.execute(statement)
    for table in TABLES:
        op.drop_table(table, schema="gamification")
    op.execute('DROP SCHEMA IF EXISTS "gamification"')
