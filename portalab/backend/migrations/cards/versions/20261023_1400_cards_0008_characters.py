"""cards — a role's own image from a community database (issue 231): looked for once per card

Revision ID: cards_0008
Revises: cards_0007
Create Date: 2026-10-23 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cards_0008"
down_revision: str | Sequence[str] | None = "cards_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("character_checked_at", sa.DateTime(timezone=True)), schema="cards")


def downgrade() -> None:
    op.drop_column("cards", "character_checked_at", schema="cards")
