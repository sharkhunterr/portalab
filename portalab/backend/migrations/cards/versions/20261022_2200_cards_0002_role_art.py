"""cards — the characters' images: an actor's card shows them in that very work (issue 229)

``sets.tmdb``: the work's TMDB id (the images a person is tagged in name it); ``cards.role_art`` /
``role_alt``: two images of the character, for the card and its borderless alternative; ``role_checked_at``:
when they were looked for (the cache — looked for once, again when the set is made again).

Revision ID: cards_0002
Revises: cards_0001
Create Date: 2026-10-22 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cards_0002"
down_revision: str | Sequence[str] | None = "cards_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sets", sa.Column("tmdb", sa.String(24), nullable=True), schema="cards")
    op.add_column("cards", sa.Column("role_art", sa.String(120), nullable=True), schema="cards")
    op.add_column("cards", sa.Column("role_alt", sa.String(120), nullable=True), schema="cards")
    op.add_column(
        "cards", sa.Column("role_checked_at", sa.DateTime(timezone=True), nullable=True), schema="cards"
    )


def downgrade() -> None:
    for column in ("role_checked_at", "role_alt", "role_art"):
        op.drop_column("cards", column, schema="cards")
    op.drop_column("sets", "tmdb", schema="cards")
