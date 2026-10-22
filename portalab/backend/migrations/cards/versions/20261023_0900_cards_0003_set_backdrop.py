"""cards — a set's backdrop: an actor's card shows them over a scene of their work (issue 229)

Revision ID: cards_0003
Revises: cards_0002
Create Date: 2026-10-23 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cards_0003"
down_revision: str | Sequence[str] | None = "cards_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sets", sa.Column("backdrop", sa.String(120), nullable=True), schema="cards")


def downgrade() -> None:
    op.drop_column("sets", "backdrop", schema="cards")
