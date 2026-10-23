"""cards — a face's height kept with its centre (a cut-out character sized by it): the faces looked for again
(issue 229)

Revision ID: cards_0014
Revises: cards_0013
Create Date: 2026-10-23 21:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "cards_0014"
down_revision: str | Sequence[str] | None = "cards_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE cards.cards SET focus = NULL WHERE focus IS NOT NULL")


def downgrade() -> None:
    pass  # the faces are looked for again by the cards on their own
