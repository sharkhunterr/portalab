"""media — a household profile's minutes on the portal (#439)

When its master counts all of Portalab as screen time (not its media only), each minute a profile spends on
the portal with its tab in view is one row; kept a week.

Revision ID: media_0029
Revises: media_0028
Create Date: 2026-11-15 07:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0029"
down_revision: str | Sequence[str] | None = "media_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "screen_beats",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("minute", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "minute", name="pk_screen_beats"),
        schema="media",
    )


def downgrade() -> None:
    op.drop_table("screen_beats", schema="media")
