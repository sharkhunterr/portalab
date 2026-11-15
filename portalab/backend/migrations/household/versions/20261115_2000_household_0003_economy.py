"""household — a master's household economy: a common pot on the master, or dispatched profiles (issue 443)

Revision ID: household_0003
Revises: household_0002
Create Date: 2026-11-15 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "household_0003"
down_revision: str | Sequence[str] | None = "household_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("economy", sa.String(10), nullable=False, server_default="pot"),
        schema="household",
    )
    op.create_check_constraint(
        op.f("ck_members_economy"), "members", "economy IN ('pot', 'dispatch')", schema="household"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_members_economy"), "members", schema="household")
    op.drop_column("members", "economy", schema="household")
