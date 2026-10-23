"""cards — a copy in its edition's version, foil or not (issue 233)

Revision ID: cards_0010
Revises: cards_0009
Create Date: 2026-10-23 17:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "cards_0010"
down_revision: str | Sequence[str] | None = "cards_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BEFORE = "('normal', 'foil', 'borderless', 'borderless_foil')"
AFTER = "('normal', 'foil', 'borderless', 'borderless_foil', 'showcase', 'showcase_foil')"


def upgrade() -> None:
    op.execute("ALTER TABLE cards.copies DROP CONSTRAINT ck_copies_variant")
    op.execute(f"ALTER TABLE cards.copies ADD CONSTRAINT ck_copies_variant CHECK (variant IN {AFTER})")


def downgrade() -> None:
    op.execute("DELETE FROM cards.copies WHERE variant IN ('showcase', 'showcase_foil')")
    op.execute("ALTER TABLE cards.copies DROP CONSTRAINT ck_copies_variant")
    op.execute(f"ALTER TABLE cards.copies ADD CONSTRAINT ck_copies_variant CHECK (variant IN {BEFORE})")
