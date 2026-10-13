"""media — the time actually watched, listened to or read in one sitting (#94)

The progression counts the minutes a member spent on a title, not its length: a live session keeps where
it started (``playback_sessions.start_position_s``) and a book or an audiobook in the portal keeps where
and when its sitting began (``book_positions.session_ref``, ``session_start_s``, ``session_started_at``).

Revision ID: media_0011
Revises: media_0010
Create Date: 2026-12-16 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0011"
down_revision: str | Sequence[str] | None = "media_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column(
        "playback_sessions", sa.Column("start_position_s", sa.Float(), nullable=True), schema="media"
    )
    op.add_column(
        "book_positions", sa.Column("session_ref", sa.String(length=64), nullable=True), schema="media"
    )
    op.add_column("book_positions", sa.Column("session_start_s", sa.Float(), nullable=True), schema="media")
    op.add_column("book_positions", sa.Column("session_started_at", TZ, nullable=True), schema="media")


def downgrade() -> None:
    op.drop_column("book_positions", "session_started_at", schema="media")
    op.drop_column("book_positions", "session_start_s", schema="media")
    op.drop_column("book_positions", "session_ref", schema="media")
    op.drop_column("playback_sessions", "start_position_s", schema="media")
