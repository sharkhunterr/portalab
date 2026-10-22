"""cards — an actor's character looked for on the web (issue 229): when it was (the cache)

Revision ID: cards_0005
Revises: cards_0004
Create Date: 2026-10-23 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cards_0005"
down_revision: str | Sequence[str] | None = "cards_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cards", sa.Column("search_checked_at", sa.DateTime(timezone=True), nullable=True), schema="cards"
    )


def downgrade() -> None:
    op.drop_column("cards", "search_checked_at", schema="cards")
