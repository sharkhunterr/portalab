"""marketplace schema — how many of a master's reserve items came from its profiles' common pot (issue 443):
given back when the master dispatches its profiles

Revision ID: marketplace_0011
Revises: marketplace_0010
Create Date: 2026-12-05 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "marketplace_0011"
down_revision: str | Sequence[str] | None = "marketplace_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reserve",
        sa.Column("household_copies", sa.Integer(), nullable=False, server_default="0"),
        schema="marketplace",
    )


def downgrade() -> None:
    op.drop_column("reserve", "household_copies", schema="marketplace")
