"""cards — an animated work's set (issue 229): its characters are drawn, no face to compare

Revision ID: cards_0006
Revises: cards_0005
Create Date: 2026-10-23 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cards_0006"
down_revision: str | Sequence[str] | None = "cards_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sets",
        sa.Column("animated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="cards",
    )


def downgrade() -> None:
    op.drop_column("sets", "animated", schema="cards")
