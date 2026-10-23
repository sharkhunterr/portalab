"""cards — a set's colour by its work's genre and the work's figures printed on its cards (issue 229)

Revision ID: cards_0009
Revises: cards_0008
Create Date: 2026-10-23 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "cards_0009"
down_revision: str | Sequence[str] | None = "cards_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sets", sa.Column("family", sa.String(12), nullable=False, server_default="drama"), schema="cards"
    )
    op.add_column(
        "sets",
        sa.Column("facts", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="cards",
    )


def downgrade() -> None:
    op.drop_column("sets", "facts", schema="cards")
    op.drop_column("sets", "family", schema="cards")
