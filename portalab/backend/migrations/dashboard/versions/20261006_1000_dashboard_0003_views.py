"""dashboard — one arrangement for every screen, or one per screen (027)

``user_dashboards.layout_mode`` (``shared`` by default: tablet and phone derive from the desktop
arrangement) and ``widget_instances.views`` (the widget's place in the tablet and phone arrangements when
the member arranges each screen on its own).

Revision ID: dashboard_0003
Revises: dashboard_0002
Create Date: 2026-10-06 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "dashboard_0003"
down_revision: str | Sequence[str] | None = "dashboard_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_dashboards",
        sa.Column("layout_mode", sa.String(length=12), nullable=False, server_default="shared"),
        schema="dashboard",
    )
    op.create_check_constraint(
        "ck_user_dashboards_layout_mode",
        "user_dashboards",
        "layout_mode IN ('shared', 'per_device')",
        schema="dashboard",
    )
    op.add_column(
        "widget_instances",
        sa.Column("views", postgresql.JSONB(), nullable=False, server_default="{}"),
        schema="dashboard",
    )


def downgrade() -> None:
    op.drop_column("widget_instances", "views", schema="dashboard")
    op.drop_constraint("ck_user_dashboards_layout_mode", "user_dashboards", schema="dashboard", type_="check")
    op.drop_column("user_dashboards", "layout_mode", schema="dashboard")
