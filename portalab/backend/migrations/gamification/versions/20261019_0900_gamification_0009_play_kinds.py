"""gamification — the kind of each rewarded play (issue 160)

``play_kinds``: an episode, a film, a book, an audiobook, live TV… for each sitting the economy rewarded
(finished or interrupted, with the time watched), so the
progression shows its gains by kind (the ledger is append-only and names only the triggering event). The
plays already rewarded get their kind from the event store where it still holds them.

Revision ID: gamification_0009
Revises: gamification_0008
Create Date: 2026-10-19 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "gamification_0009"
down_revision: str | Sequence[str] | None = "gamification_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = ("events_0001",)

TZ = sa.DateTime(timezone=True)

BACKFILL = """
INSERT INTO gamification.play_kinds (event_id, user_id, kind, object, finished, watched_s, occurred_at)
SELECT DISTINCT ON (t.trigger_event_id)
    t.trigger_event_id, t.user_id, left(e.payload->>'kind', 24), left(e.payload->>'object', 64),
    e.type = 'media.playback_finished',
    least(greatest(coalesce((e.payload->>'watched_s')::float, 0), 0), 86400)::int,
    t.occurred_at
FROM gamification.transactions t
JOIN events.events e ON e.event_id = t.trigger_event_id
WHERE t.trigger_event_id IS NOT NULL
  AND e.type IN ('media.playback_finished', 'media.playback_abandoned')
  AND coalesce(e.payload->>'kind', '') <> ''
ORDER BY t.trigger_event_id, t.occurred_at
ON CONFLICT DO NOTHING
"""


def upgrade() -> None:
    op.create_table(
        "play_kinds",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("object", sa.String(64), nullable=True),
        sa.Column("finished", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("watched_s", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("event_id", name="pk_play_kinds"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_play_kinds_user", ondelete="CASCADE"
        ),
        schema="gamification",
    )
    op.create_index(
        "ix_play_kinds_user_occurred", "play_kinds", ["user_id", "occurred_at"], schema="gamification"
    )
    op.execute(BACKFILL)


def downgrade() -> None:
    op.drop_table("play_kinds", schema="gamification")
