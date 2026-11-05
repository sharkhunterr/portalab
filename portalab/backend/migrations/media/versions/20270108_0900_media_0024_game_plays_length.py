"""media — a game played lasts what it was played (#351)

Since RomM tells how long a game takes (HowLongToBeat), a game's play stored without its minutes (« played
on that day ») took that length as its time, as a film seen without minutes takes the film's: a few minutes'
session counted hours. A game's play keeps no length of the game's, and one told without its minutes has
none; their days are counted again.

Revision ID: media_0024
Revises: media_0023
Create Date: 2026-11-05 08:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0024"
down_revision: str | Sequence[str] | None = "media_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO media.activity_dirty_days (day)"
            " SELECT DISTINCT date_trunc('day', started_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'"
            " FROM media.activity WHERE kind = 'game' AND duration_s IS NOT NULL ON CONFLICT DO NOTHING"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE media.activity SET watched_s = CASE WHEN watched_s = duration_s THEN 0 ELSE watched_s END,"
            " duration_s = NULL WHERE kind = 'game' AND duration_s IS NOT NULL"
        )
    )


def downgrade() -> None:
    pass  # the lengths taken were wrong
