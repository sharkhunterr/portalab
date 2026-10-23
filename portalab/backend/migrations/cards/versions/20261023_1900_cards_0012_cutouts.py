"""cards — each card's character cut out of the image it shows (issue 229)

Revision ID: cards_0012
Revises: cards_0011
Create Date: 2026-10-23 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "cards_0012"
down_revision: str | Sequence[str] | None = "cards_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("cutout", JSONB(), nullable=True), schema="cards")


def downgrade() -> None:
    op.drop_column("cards", "cutout", schema="cards")
