"""gamification — the days counted by play streaks (027)

Revision ID: gamification_0004
Revises: gamification_0003
Create Date: 2026-10-06 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "gamification_0004"
down_revision: str | Sequence[str] | None = "gamification_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "streak_days",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "day", name="pk_streak_days"),
        schema="gamification",
    )


def downgrade() -> None:
    op.drop_table("streak_days", schema="gamification")
