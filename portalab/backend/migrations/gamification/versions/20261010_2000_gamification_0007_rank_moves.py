"""gamification schema — leaderboards remember the ranking of a day before (#66)

``leaderboard_snapshots.previous``: the ``[user_id, score]`` pairs of the same board as it stood 24 hours
earlier, rebuilt with the snapshot — read to tell who gained or lost places (visibility applied at read).

Revision ID: gamification_0007
Revises: gamification_0006
Create Date: 2026-10-10 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "gamification_0007"
down_revision: str | Sequence[str] | None = "gamification_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leaderboard_snapshots",
        sa.Column("previous", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        schema="gamification",
    )


def downgrade() -> None:
    op.drop_column("leaderboard_snapshots", "previous", schema="gamification")
