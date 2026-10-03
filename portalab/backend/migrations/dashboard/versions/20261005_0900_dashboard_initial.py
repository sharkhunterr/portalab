"""dashboard initial schema — per-user dashboard rows and widget instances (spec 009 T007)

Revision ID: dashboard_0001
Revises:
Create Date: 2026-10-05 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dashboard_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("dashboard",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "dashboard"')
    op.create_table(
        "user_dashboards",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("starter_applied_at", TZ),
        sa.Column("last_summary_seen_at", TZ),
        sa.Column("layout_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_dashboards"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_user_dashboards_user_id_users", ondelete="CASCADE"
        ),
        schema="dashboard",
    )
    op.create_table(
        "widget_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("widget_key", sa.String(96), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("w", sa.Integer(), nullable=False),
        sa.Column("h", sa.Integer(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("config_schema_version", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_widget_instances"),
        sa.CheckConstraint("status IN ('active', 'hidden')", name="ck_widget_instances_status"),
        sa.CheckConstraint(
            "origin IN ('starter', 'user', 'policy_default')", name="ck_widget_instances_origin"
        ),
        sa.CheckConstraint("w BETWEEN 1 AND 12 AND h BETWEEN 1 AND 12", name="ck_widget_instances_size"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_widget_instances_user_id_users", ondelete="CASCADE"
        ),
        schema="dashboard",
    )
    op.create_index(
        "ix_widget_instances_user_position", "widget_instances", ["user_id", "position"], schema="dashboard"
    )


def downgrade() -> None:
    op.drop_index("ix_widget_instances_user_position", table_name="widget_instances", schema="dashboard")
    op.drop_table("widget_instances", schema="dashboard")
    op.drop_table("user_dashboards", schema="dashboard")
