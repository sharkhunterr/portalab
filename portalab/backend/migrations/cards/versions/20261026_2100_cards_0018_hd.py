"""cards — a legendary's copy in its edition's HD version (issue 255)

Revision ID: cards_0018
Revises: cards_0017
Create Date: 2026-10-26 21:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "cards_0018"
down_revision: str | Sequence[str] | None = "cards_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BEFORE = "('normal', 'foil', 'borderless', 'borderless_foil', 'showcase', 'showcase_foil')"
AFTER = "('normal', 'foil', 'borderless', 'borderless_foil', 'showcase', 'showcase_foil', 'hd')"


def upgrade() -> None:
    op.execute("ALTER TABLE cards.copies DROP CONSTRAINT ck_copies_variant")
    op.execute(f"ALTER TABLE cards.copies ADD CONSTRAINT ck_copies_variant CHECK (variant IN {AFTER})")


def downgrade() -> None:
    op.execute("DELETE FROM cards.copies WHERE variant = 'hd'")
    op.execute("ALTER TABLE cards.copies DROP CONSTRAINT ck_copies_variant")
    op.execute(f"ALTER TABLE cards.copies ADD CONSTRAINT ck_copies_variant CHECK (variant IN {BEFORE})")
