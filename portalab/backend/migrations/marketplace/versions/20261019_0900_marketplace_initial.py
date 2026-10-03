"""marketplace schema — community projects, state history, fundings, notes

Revision ID: marketplace_0001
Revises:
Create Date: 2026-10-19 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "marketplace_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("marketplace",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
TABLES = ("project_state_history", "project_notes", "project_fundings", "projects")


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "marketplace"')
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_ref", sa.String(length=64), nullable=False),
        sa.Column("proposer_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("funding_rules", postgresql.JSONB(), nullable=True),
        sa.Column("rules_frozen_at", TZ, nullable=True),
        sa.Column("goal_amount", sa.BigInteger(), nullable=True),
        sa.Column("validated_by", sa.Uuid(), nullable=True),
        sa.Column("validated_at", TZ, nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint(
            "state IN ('idea', 'proposal', 'open', 'validation', 'development', 'beta', 'released', 'rejected', 'abandoned')",
            name="ck_projects_state",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("proposal_ref", name="uq_projects_proposal_ref"),
        _user_fk("projects", "proposer_id", "SET NULL"),
        schema="marketplace",
    )
    op.create_table(
        "project_fundings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("tranches", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("acknowledged_at", TZ, nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("resolved_at", TZ, nullable=True),
        sa.CheckConstraint(
            "status IN ('reserved', 'released', 'consumed', 'partially_consumed', 'destroyed_on_deletion')",
            name="ck_project_fundings_status",
        ),
        sa.CheckConstraint("amount > 0", name="ck_project_fundings_amount"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["marketplace.projects.id"], name="fk_project_fundings_project_id_projects"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_fundings"),
        sa.UniqueConstraint("idempotency_key", name="uq_project_fundings_idempotency_key"),
        _user_fk("project_fundings", "user_id", "RESTRICT"),
        schema="marketplace",
    )
    op.create_index(
        "ix_project_fundings_project_status",
        "project_fundings",
        ["project_id", "status"],
        unique=False,
        schema="marketplace",
    )
    op.create_index(
        "ix_project_fundings_user",
        "project_fundings",
        ["user_id", "created_at"],
        unique=False,
        schema="marketplace",
    )
    op.create_table(
        "project_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("public_note", sa.Text(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["marketplace.projects.id"], name="fk_project_notes_project_id_projects"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_notes"),
        _user_fk("project_notes", "author_id", "SET NULL"),
        schema="marketplace",
    )
    op.create_table(
        "project_state_history",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.String(length=12), nullable=True),
        sa.Column("to_state", sa.String(length=12), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["marketplace.projects.id"], name="fk_project_state_history_project_id_projects"
        ),
        sa.PrimaryKeyConstraint("project_id", "seq", name="pk_project_state_history"),
        _user_fk("project_state_history", "actor_user_id", "RESTRICT"),
        schema="marketplace",
        info={"portalab_append_only": True},
    )
    op.create_foreign_key(
        "fk_projects_validated_by_users",
        "projects",
        "users",
        ["validated_by"],
        ["id"],
        source_schema="marketplace",
        referent_schema="identity",
        ondelete="SET NULL",
    )
    for statement in append_only_ddl("marketplace", "project_state_history"):
        op.execute(statement)


def downgrade() -> None:
    for statement in drop_append_only_ddl("marketplace", "project_state_history"):
        op.execute(statement)
    for table in TABLES:
        op.drop_table(table, schema="marketplace")
    op.execute('DROP SCHEMA IF EXISTS "marketplace"')
