"""stats schema — statistic definitions (append-only versions) and their status, daily buckets, distinct
members, applied-event ledger, projection watermarks, unlocks, Wrapped definitions and immutable
snapshots, rebuild runs (spec 017 T006)

Revision ID: stats_0001
Revises:
Create Date: 2026-10-07 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "stats_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("stats",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)

SNAPSHOT_IMMUTABLE = """
CREATE OR REPLACE FUNCTION stats.protect_snapshots() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Wrapped snapshots are immutable' USING ERRCODE = 'P0001';
END;
$$
"""
SNAPSHOT_TRIGGER = """
CREATE TRIGGER wrapped_snapshots_immutable BEFORE UPDATE ON stats.wrapped_snapshots
FOR EACH ROW EXECUTE FUNCTION stats.protect_snapshots()
"""


def _scope(table: str) -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("stat_key", sa.String(96), nullable=False),
        sa.Column("def_version", sa.Integer(), nullable=False),
        sa.Column("scope_type", sa.String(10), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("bucket_day", sa.Date(), nullable=False),
        sa.Column("dims_hash", sa.String(40), nullable=False),
    ]


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "stats"')
    op.create_table(
        "definitions",
        sa.Column("key", sa.String(96), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("change_policy", sa.String(16), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("key", "version", name="pk_definitions"),
        sa.CheckConstraint(
            "change_policy IN ('forward_only', 'rebuild')", name="ck_definitions_change_policy"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["identity.users.id"], name="fk_definitions_created_by_users"
        ),
        schema="stats",
    )
    for statement in append_only_ddl("stats", "definitions"):
        op.execute(statement)
    op.create_table(
        "definition_status",
        sa.Column("key", sa.String(96), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("active_version", sa.Integer()),
        sa.Column("latest_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_definition_status"),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_definition_status_status"),
        schema="stats",
    )
    op.create_table(
        "buckets",
        *_scope("buckets"),
        sa.Column("dims", postgresql.JSONB(), nullable=False),
        sa.Column("count", sa.BigInteger(), nullable=False),
        sa.Column("sum", sa.Numeric(), nullable=False),
        sa.Column("min", sa.Numeric()),
        sa.Column("max", sa.Numeric()),
        sa.PrimaryKeyConstraint(
            "stat_key", "def_version", "scope_type", "scope_id", "bucket_day", "dims_hash", name="pk_buckets"
        ),
        schema="stats",
    )
    op.create_table(
        "members",
        *_scope("members"),
        sa.Column("member_hash", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint(
            "stat_key",
            "def_version",
            "scope_type",
            "scope_id",
            "bucket_day",
            "dims_hash",
            "member_hash",
            name="pk_members",
        ),
        schema="stats",
    )
    op.create_table(
        "applied_events",
        sa.Column("stat_key", sa.String(96), nullable=False),
        sa.Column("def_version", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("bucket_day", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("stat_key", "def_version", "event_id", name="pk_applied_events"),
        schema="stats",
    )
    op.create_table(
        "projection_state",
        sa.Column("stat_key", sa.String(96), nullable=False),
        sa.Column("def_version", sa.Integer(), nullable=False),
        sa.Column("last_event_at", TZ),
        sa.Column("events", sa.BigInteger(), nullable=False),
        sa.Column("start_after_seq", sa.BigInteger()),
        sa.Column("stop_after_seq", sa.BigInteger()),
        sa.Column("lineage_from", sa.Integer()),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("stat_key", "def_version", name="pk_projection_state"),
        schema="stats",
    )
    op.create_table(
        "unlocks",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("stat_key", sa.String(96), nullable=False),
        sa.Column("unlocked_at", TZ, nullable=False),
        sa.Column("reason", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "stat_key", name="pk_unlocks"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_unlocks_user_id_users", ondelete="CASCADE"
        ),
        schema="stats",
    )
    op.create_table(
        "wrapped_definitions",
        sa.Column("key", sa.String(96), nullable=False),
        sa.Column("period_kind", sa.String(8), nullable=False),
        sa.Column("stat_keys", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_wrapped_definitions"),
        sa.CheckConstraint(
            "period_kind IN ('month', 'quarter', 'year')", name="ck_wrapped_definitions_period_kind"
        ),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_wrapped_definitions_status"),
        schema="stats",
    )
    op.create_table(
        "wrapped_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wrapped_key", sa.String(96), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("subject_scope", sa.String(10), nullable=False),
        sa.Column("user_id", sa.Uuid()),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("generated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_wrapped_snapshots"),
        sa.CheckConstraint(
            "subject_scope IN ('user', 'community')", name="ck_wrapped_snapshots_subject_scope"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_wrapped_snapshots_user_id_users", ondelete="CASCADE"
        ),
        schema="stats",
    )
    op.execute(SNAPSHOT_IMMUTABLE)
    op.execute(SNAPSHOT_TRIGGER)
    op.create_table(
        "rebuild_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stat_key", sa.String(96), nullable=False),
        sa.Column("def_version", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Uuid()),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("finished_at", TZ),
        sa.PrimaryKeyConstraint("id", name="pk_rebuild_runs"),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["identity.users.id"], name="fk_rebuild_runs_requested_by_users"
        ),
        schema="stats",
    )


def downgrade() -> None:
    op.drop_table("rebuild_runs", schema="stats")
    op.execute("DROP TRIGGER IF EXISTS wrapped_snapshots_immutable ON stats.wrapped_snapshots")
    op.drop_table("wrapped_snapshots", schema="stats")
    op.execute("DROP FUNCTION IF EXISTS stats.protect_snapshots()")
    for name in (
        "wrapped_definitions",
        "unlocks",
        "projection_state",
        "applied_events",
        "members",
        "buckets",
        "definition_status",
    ):
        op.drop_table(name, schema="stats")
    for statement in drop_append_only_ddl("stats", "definitions"):
        op.execute(statement)
    op.drop_table("definitions", schema="stats")
