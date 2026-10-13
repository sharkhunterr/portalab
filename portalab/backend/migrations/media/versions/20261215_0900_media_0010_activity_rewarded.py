"""media — a play turned into the progression once (#94)

``media.activity.rewarded_at``: when a finished play recorded by a service's history (the live watch
missed it) was published as ``media.playback_finished`` for the progression — at most once.

Revision ID: media_0010
Revises: media_0009
Create Date: 2026-12-15 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0010"
down_revision: str | Sequence[str] | None = "media_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "activity", sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True), schema="media"
    )


def downgrade() -> None:
    op.drop_column("activity", "rewarded_at", schema="media")
