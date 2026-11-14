"""household — what a master gives a profile for a while: minutes more on one day, no limits until a moment
(issue 432).

Revision ID: household_0002
Revises: household_0001
Create Date: 2026-11-15 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "household_0002"
down_revision: str | Sequence[str] | None = "household_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "members",
        sa.Column("bonus_minutes", sa.Integer(), nullable=False, server_default="0"),
        schema="household",
    )
    op.add_column("members", sa.Column("bonus_day", sa.Date(), nullable=True), schema="household")
    op.add_column(
        "members", sa.Column("free_until", sa.DateTime(timezone=True), nullable=True), schema="household"
    )


def downgrade() -> None:
    for column in ("free_until", "bonus_day", "bonus_minutes"):
        op.drop_column("members", column, schema="household")
