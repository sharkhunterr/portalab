"""dashboard 2D arrangement — x/y grid coordinates back-filled from the ordered layout (spec 027 T071, R14)

Every user's widgets are flowed into the 12-column grid in their stored order (row packing, the engine's
``flow``), so no widget, size or configuration is lost; then the columns become NOT NULL and a check keeps
widgets inside the grid.

Revision ID: dashboard_0002
Revises: dashboard_0001
Create Date: 2026-10-04 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dashboard_0002"
down_revision: str | Sequence[str] | None = "dashboard_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = 12


def upgrade() -> None:
    op.add_column("widget_instances", sa.Column("x", sa.Integer(), nullable=True), schema="dashboard")
    op.add_column("widget_instances", sa.Column("y", sa.Integer(), nullable=True), schema="dashboard")
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, user_id, w, h FROM dashboard.widget_instances "
            "ORDER BY user_id, CASE status WHEN 'active' THEN 0 ELSE 1 END, position, id"
        )
    ).all()
    user = None
    x = y = row_height = 0
    for instance_id, owner, w, h in rows:
        if owner != user:
            user, x, y, row_height = owner, 0, 0, 0
        width = min(int(w), COLUMNS)
        if x + width > COLUMNS:
            x, y, row_height = 0, y + row_height, 0
        bind.execute(
            sa.text("UPDATE dashboard.widget_instances SET x = :x, y = :y, w = :w WHERE id = :id"),
            {"x": x, "y": y, "w": width, "id": instance_id},
        )
        x += width
        row_height = max(row_height, int(h))
    op.alter_column("widget_instances", "x", nullable=False, server_default="0", schema="dashboard")
    op.alter_column("widget_instances", "y", nullable=False, server_default="0", schema="dashboard")
    op.create_check_constraint(
        "ck_widget_instances_grid",
        "widget_instances",
        "x >= 0 AND x + w <= 12 AND y >= 0",
        schema="dashboard",
    )
    op.create_index(
        "ix_widget_instances_user_grid", "widget_instances", ["user_id", "y", "x"], schema="dashboard"
    )


def downgrade() -> None:
    op.drop_index("ix_widget_instances_user_grid", table_name="widget_instances", schema="dashboard")
    op.drop_constraint("ck_widget_instances_grid", "widget_instances", schema="dashboard")
    op.drop_column("widget_instances", "y", schema="dashboard")
    op.drop_column("widget_instances", "x", schema="dashboard")
