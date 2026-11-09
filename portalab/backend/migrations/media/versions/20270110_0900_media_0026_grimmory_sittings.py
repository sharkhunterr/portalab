"""media — Grimmory's pieces of one sitting become that sitting (#385)

Grimmory saves a listening sitting in pieces of a few minutes, all from the sitting's start; each piece was
stored as a play of its own. The pieces of one sitting (same service, book and start) are now one row: the
first piece's (its ref is the sitting's from now on), the minutes added up, the last piece's end and
progress. Their days are rebuilt. The XP the pieces earned stays earned; the sitting's finish, when the book
reached its end, comes at the next reading of Grimmory's history (#386).

Revision ID: media_0026
Revises: media_0025
Create Date: 2026-11-09 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0026"
down_revision: str | Sequence[str] | None = "media_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PIECES = """
    SELECT a.id, a.started_at,
           row_number() OVER sitting AS n,
           count(*) OVER sitting AS pieces,
           sum(a.watched_s) OVER sitting AS watched,
           max(a.stopped_at) OVER sitting AS ended,
           last_value(a.progress) OVER (
               PARTITION BY a.service_id, a.item_external_id, a.started_at
               ORDER BY a.progress IS NOT NULL, a.stopped_at
               ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
           ) AS progress
    FROM media.activity a
    JOIN connectors.services s ON s.id = a.service_id AND s.connector_key = 'grimmory'
    WHERE a.ref ~ '^[0-9]+$' AND a.item_external_id IS NOT NULL
    WINDOW sitting AS (
        PARTITION BY a.service_id, a.item_external_id, a.started_at
        ORDER BY a.ref::bigint
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    )
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT to_regclass('connectors.services')")) is None:
        return  # a fresh portal: no Grimmory history yet
    bind.execute(sa.text("CREATE TEMPORARY TABLE grimmory_pieces ON COMMIT DROP AS" + PIECES))
    bind.execute(
        sa.text(
            "INSERT INTO media.activity_dirty_days (day)"
            " SELECT DISTINCT date_trunc('day', started_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'"
            " FROM grimmory_pieces WHERE pieces > 1 ON CONFLICT DO NOTHING"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE media.activity a SET watched_s = p.watched, stopped_at = p.ended, progress = p.progress"
            " FROM grimmory_pieces p WHERE a.id = p.id AND p.n = 1 AND p.pieces > 1"
        )
    )
    bind.execute(
        sa.text("DELETE FROM media.activity a USING grimmory_pieces p WHERE a.id = p.id AND p.n > 1")
    )
    bind.execute(sa.text("DROP TABLE grimmory_pieces"))


def downgrade() -> None:
    pass  # the pieces are not split again
