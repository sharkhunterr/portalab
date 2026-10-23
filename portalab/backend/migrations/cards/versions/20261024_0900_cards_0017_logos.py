"""cards — a work's title drawn (its HD logos, per language), for its boosters (issue 234)

Revision ID: cards_0017
Revises: cards_0016
Create Date: 2026-10-24 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "cards_0017"
down_revision: str | Sequence[str] | None = "cards_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sets", sa.Column("logos", JSONB(), nullable=True), schema="cards")
    # the works' art looked for again: their logos kept this time
    op.execute("UPDATE cards.cards SET fan_checked_at = NULL WHERE kind = 'title'")


def downgrade() -> None:
    op.drop_column("sets", "logos", schema="cards")
