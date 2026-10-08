"""media — how each play was streamed and in which resolution (027)

``activity.stream`` (direct, copy, transcode) and ``activity.quality`` (4k, 1080p, 720p, sd), when the
source tells (Tautulli).

Revision ID: media_0004
Revises: media_0003
Create Date: 2026-11-15 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0004"
down_revision: str | Sequence[str] | None = "media_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("activity", sa.Column("stream", sa.String(12), nullable=True), schema="media")
    op.add_column("activity", sa.Column("quality", sa.String(12), nullable=True), schema="media")


def downgrade() -> None:
    op.drop_column("activity", "quality", schema="media")
    op.drop_column("activity", "stream", schema="media")
