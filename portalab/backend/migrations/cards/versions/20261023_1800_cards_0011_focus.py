"""cards — where the face is in each image a card shows (issue 229)

Revision ID: cards_0011
Revises: cards_0010
Create Date: 2026-10-23 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "cards_0011"
down_revision: str | Sequence[str] | None = "cards_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("focus", JSONB(), nullable=True), schema="cards")


def downgrade() -> None:
    op.drop_column("cards", "focus", schema="cards")
