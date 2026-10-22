"""cards — a work's art from an art site (fanart.tv) for its borderless alternative (issue 229)

``cards.fan_art``: the work's card's full art (a textless background, the best liked); ``fan_checked_at``:
when it was looked for (the cache).

Revision ID: cards_0004
Revises: cards_0003
Create Date: 2026-10-23 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cards_0004"
down_revision: str | Sequence[str] | None = "cards_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("fan_art", sa.String(240), nullable=True), schema="cards")
    op.add_column(
        "cards", sa.Column("fan_checked_at", sa.DateTime(timezone=True), nullable=True), schema="cards"
    )
    op.add_column("sets", sa.Column("ids", sa.String(240), nullable=True), schema="cards")


def downgrade() -> None:
    op.drop_column("sets", "ids", schema="cards")
    op.drop_column("cards", "fan_checked_at", schema="cards")
    op.drop_column("cards", "fan_art", schema="cards")
