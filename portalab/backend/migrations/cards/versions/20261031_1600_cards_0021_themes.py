"""cards — a work's themes, a theme booster's works (issue 296)

Revision ID: cards_0021
Revises: cards_0020
Create Date: 2026-10-31 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "cards_0021"
down_revision: str | Sequence[str] | None = "cards_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # filled when the sets are made again: their fingerprint now counts their themes
    op.add_column(
        "sets",
        sa.Column("themes", ARRAY(sa.String(16)), nullable=False, server_default="{}"),
        schema="cards",
    )


def downgrade() -> None:
    op.drop_column("sets", "themes", schema="cards")
