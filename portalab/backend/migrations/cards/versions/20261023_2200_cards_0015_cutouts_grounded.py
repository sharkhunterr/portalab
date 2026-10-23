"""cards — the characters cut out again, a head kept alone (its body lost) left as its photograph (issue 229)

Revision ID: cards_0015
Revises: cards_0014
Create Date: 2026-10-23 22:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "cards_0015"
down_revision: str | Sequence[str] | None = "cards_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE cards.cards SET cutout = NULL WHERE cutout IS NOT NULL")


def downgrade() -> None:
    pass  # the cut-outs are made again by the cards on their own
