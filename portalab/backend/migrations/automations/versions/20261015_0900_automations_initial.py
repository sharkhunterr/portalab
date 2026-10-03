"""automations schema — automations, versions, executions, approvals

Revision ID: automations_0001
Revises:
Create Date: 2026-10-15 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "automations_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("automations",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
TABLES = (
    "approvals",
    "versions",
    "schedule_state",
    "pending_fires",
    "executions",
    "dedup_windows",
    "automations",
)


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "automations"')
    op.create_table(
        "automations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("published_version", sa.Integer(), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("identity_kind", sa.String(length=8), nullable=False),
        sa.Column("system_scopes", postgresql.JSONB(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.Column("suspend_reason", sa.String(length=200), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("identity_kind IN ('author', 'system')", name="ck_automations_identity_kind"),
        sa.CheckConstraint(
            "state IN ('draft', 'active', 'paused', 'suspended', 'archived')", name="ck_automations_state"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_automations"),
        sa.UniqueConstraint("key", name="uq_automations_key"),
        _user_fk("automations", "owner_user_id", "RESTRICT"),
        schema="automations",
    )
    op.create_table(
        "dedup_windows",
        sa.Column("automation_id", sa.Uuid(), nullable=False),
        sa.Column("dedup_key", sa.String(length=200), nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automations.automations.id"],
            name="fk_dedup_windows_automation_id_automations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("automation_id", "dedup_key", name="pk_dedup_windows"),
        schema="automations",
    )
    op.create_table(
        "executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("automation_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("trigger_event_id", sa.Uuid(), nullable=True),
        sa.Column("trigger_ref", postgresql.JSONB(), nullable=False),
        sa.Column("chain_id", sa.String(length=64), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("conditions_trace", postgresql.JSONB(), nullable=False),
        sa.Column("steps", postgresql.JSONB(), nullable=False),
        sa.Column("batch_count", sa.Integer(), nullable=False),
        sa.Column("principal", postgresql.JSONB(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("finished_at", TZ, nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'no_op', 'refused', 'prevented', 'timeout', 'suspended', 'failed', 'throttled', 'awaiting_approval')",
            name="ck_executions_status",
        ),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automations.automations.id"],
            name="fk_executions_automation_id_automations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_executions"),
        schema="automations",
    )
    op.create_index(
        "ix_executions_automation",
        "executions",
        ["automation_id", "started_at"],
        unique=False,
        schema="automations",
    )
    op.create_index("ix_executions_chain", "executions", ["chain_id"], unique=False, schema="automations")
    op.create_index(
        "uq_executions_trigger",
        "executions",
        ["automation_id", "version", "trigger_event_id"],
        unique=True,
        schema="automations",
        postgresql_where=sa.text("trigger_event_id IS NOT NULL"),
    )
    op.create_table(
        "pending_fires",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("automation_id", sa.Uuid(), nullable=False),
        sa.Column("source_event_id", sa.Uuid(), nullable=False),
        sa.Column("fire_at", TZ, nullable=False),
        sa.Column("fired", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automations.automations.id"],
            name="fk_pending_fires_automation_id_automations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pending_fires"),
        sa.UniqueConstraint("automation_id", "source_event_id", name="uq_pending_fires_source"),
        schema="automations",
    )
    op.create_index("ix_pending_fires_due", "pending_fires", ["fire_at"], unique=False, schema="automations")
    op.create_table(
        "schedule_state",
        sa.Column("automation_id", sa.Uuid(), nullable=False),
        sa.Column("next_fire_at", TZ, nullable=True),
        sa.Column("last_fired_at", TZ, nullable=True),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automations.automations.id"],
            name="fk_schedule_state_automation_id_automations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("automation_id", name="pk_schedule_state"),
        schema="automations",
    )
    op.create_table(
        "versions",
        sa.Column("automation_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", TZ, nullable=False),
        sa.Column("standing_approvals", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["automation_id"], ["automations.automations.id"], name="fk_versions_automation_id_automations"
        ),
        sa.PrimaryKeyConstraint("automation_id", "version", name="pk_versions"),
        schema="automations",
        info={"portalab_append_only": True},
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("summary", sa.String(length=400), nullable=False),
        sa.Column("params_hash", sa.String(length=64), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", TZ, nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired')", name="ck_approvals_status"
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["automations.executions.id"],
            name="fk_approvals_execution_id_executions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_approvals"),
        sa.UniqueConstraint("execution_id", "step_id", name="uq_approvals_step"),
        schema="automations",
    )
    op.create_index(
        "ix_approvals_status", "approvals", ["status", "expires_at"], unique=False, schema="automations"
    )
    for statement in append_only_ddl("automations", "versions"):
        op.execute(statement)


def downgrade() -> None:
    for statement in drop_append_only_ddl("automations", "versions"):
        op.execute(statement)
    for table in TABLES:
        op.drop_table(table, schema="automations")
    op.execute('DROP SCHEMA IF EXISTS "automations"')
