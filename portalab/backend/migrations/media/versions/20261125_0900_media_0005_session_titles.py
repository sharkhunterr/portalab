"""media — what a session is called when the library cannot resolve it (#47)

``playback_sessions.title``, ``subtitle`` (the episode under its series) and ``channel`` (live TV), as the
source names them.

Revision ID: media_0005
Revises: media_0004
Create Date: 2026-11-25 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0005"
down_revision: str | Sequence[str] | None = "media_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("playback_sessions", sa.Column("title", sa.String(500), nullable=True), schema="media")
    op.add_column("playback_sessions", sa.Column("subtitle", sa.String(500), nullable=True), schema="media")
    op.add_column("playback_sessions", sa.Column("channel", sa.String(200), nullable=True), schema="media")


def downgrade() -> None:
    op.drop_column("playback_sessions", "channel", schema="media")
    op.drop_column("playback_sessions", "subtitle", schema="media")
    op.drop_column("playback_sessions", "title", schema="media")
