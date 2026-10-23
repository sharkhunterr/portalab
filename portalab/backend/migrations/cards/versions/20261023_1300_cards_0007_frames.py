"""cards — an actor's character taken from the film itself (issue 230): looked for once per card

Revision ID: cards_0007
Revises: cards_0006
Create Date: 2026-10-23 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cards_0007"
down_revision: str | Sequence[str] | None = "cards_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("frame_checked_at", sa.DateTime(timezone=True)), schema="cards")


def downgrade() -> None:
    op.drop_column("cards", "frame_checked_at", schema="cards")
