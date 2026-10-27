"""media — a sitting in the portal ends, even when the member never says so (#256)

A book or an audiobook read or heard in the portal counts its minutes when its sitting ends: the member closes
it, finishes it or leaves the page — or, when the page went away silently (a phone's app closed), the sitting
is ended once nothing has been heard of it for a while. ``session_ended_at`` says it is over (counted once),
``session_watched_s`` keeps the minutes it had reached for that ending.

The sittings already there are taken as over: whether one was closed (its minutes counted then) or only paused
cannot be told apart, and counting it now could count it twice.

Revision ID: media_0013
Revises: media_0012
Create Date: 2026-10-27 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0013"
down_revision: str | Sequence[str] | None = "media_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("book_positions", sa.Column("session_ended_at", TZ, nullable=True), schema="media")
    op.add_column("book_positions", sa.Column("session_watched_s", sa.Float(), nullable=True), schema="media")
    op.execute(
        "UPDATE media.book_positions SET session_ended_at = updated_at WHERE session_started_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("book_positions", "session_watched_s", schema="media")
    op.drop_column("book_positions", "session_ended_at", schema="media")
