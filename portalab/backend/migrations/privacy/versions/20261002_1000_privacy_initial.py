"""privacy initial schema — visibility policies, retention runs (spec 021 T006)

Revision ID: privacy_0001
Revises:
Create Date: 2026-10-02 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "privacy_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("privacy",)
depends_on: str | Sequence[str] | None = ("identity_0001",)

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "privacy"')
    op.create_table(
        "visibility_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_user_id", sa.Uuid()),
        sa.Column("datum_class", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("level", sa.String(16)),
        sa.Column("reason", sa.String(256), nullable=False),
        sa.Column("set_by", sa.Uuid()),
        sa.Column("set_at", TZ, nullable=False),
        sa.Column("ends_at", TZ),
        sa.Column("removed_at", TZ),
        sa.Column("removed_by", sa.Uuid()),
        sa.PrimaryKeyConstraint("id", name="pk_visibility_policies"),
        sa.ForeignKeyConstraint(
            ["subject_user_id"], ["identity.users.id"], name="fk_visibility_policies_subject_user_id_users"
        ),
        sa.CheckConstraint(
            "mode IN ('user_choice', 'force_visible', 'force_private')", name="ck_visibility_policies_mode"
        ),
        sa.CheckConstraint(
            "level IS NULL OR level IN ('public', 'community', 'leaderboard', 'private')",
            name="ck_visibility_policies_level",
        ),
        sa.CheckConstraint(
            "(mode = 'user_choice' AND level IS NULL) OR (mode = 'force_private' AND level = 'private') "
            "OR (mode = 'force_visible' AND level IN ('public', 'community', 'leaderboard'))",
            name="ck_visibility_policies_mode_level",
        ),
        schema="privacy",
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_visibility_policies_active ON privacy.visibility_policies "
        "(subject_user_id, datum_class) NULLS NOT DISTINCT WHERE removed_at IS NULL"
    )
    op.create_table(
        "retention_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("target", sa.String(128), nullable=False),
        sa.Column("data_class", sa.String(16), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("rows_affected", sa.Integer(), nullable=False),
        sa.Column("cutoff", TZ, nullable=False),
        sa.Column("run_at", TZ, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.String(256)),
        sa.PrimaryKeyConstraint("id", name="pk_retention_runs"),
        schema="privacy",
    )
    for statement in append_only_ddl("privacy", "retention_runs"):
        op.execute(statement)


def downgrade() -> None:
    for statement in drop_append_only_ddl("privacy", "retention_runs"):
        op.execute(statement)
    op.drop_table("retention_runs", schema="privacy")
    op.drop_table("visibility_policies", schema="privacy")
    op.execute('DROP SCHEMA IF EXISTS "privacy"')
