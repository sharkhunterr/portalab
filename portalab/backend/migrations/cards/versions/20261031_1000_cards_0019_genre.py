"""cards — a copy in its genre's version, its genre's frame (issue 295)

Revision ID: cards_0019
Revises: cards_0018
Create Date: 2026-10-31 10:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "cards_0019"
down_revision: str | Sequence[str] | None = "cards_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BEFORE = "('normal', 'foil', 'borderless', 'borderless_foil', 'showcase', 'showcase_foil', 'hd')"
AFTER = "('normal', 'foil', 'borderless', 'borderless_foil', 'showcase', 'showcase_foil', 'hd', 'genre', 'genre_foil')"


def upgrade() -> None:
    op.execute("ALTER TABLE cards.copies DROP CONSTRAINT ck_copies_variant")
    op.execute(f"ALTER TABLE cards.copies ADD CONSTRAINT ck_copies_variant CHECK (variant IN {AFTER})")


def downgrade() -> None:
    op.execute("DELETE FROM cards.copies WHERE variant IN ('genre', 'genre_foil')")
    op.execute("ALTER TABLE cards.copies DROP CONSTRAINT ck_copies_variant")
    op.execute(f"ALTER TABLE cards.copies ADD CONSTRAINT ck_copies_variant CHECK (variant IN {BEFORE})")
