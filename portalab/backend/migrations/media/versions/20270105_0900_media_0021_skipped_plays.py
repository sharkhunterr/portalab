"""media — the recent plays skipped for a history session are looked at again (#340)

A play read from Plex's own history (``…:history:…``, without its minutes) was taken for a play followed
live: another history's play of it (Tautulli's) was marked looked at, nothing published. The plays of the
last 48 hours (the catch-up's window) marked that way are looked at again; one the live watch did follow is
still skipped, and an event already published is never published twice (its dedup key).

Revision ID: media_0021
Revises: media_0020
Create Date: 2026-11-02 19:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "media_0021"
down_revision: str | Sequence[str] | None = "media_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE media.activity a SET rewarded_at = NULL
        WHERE a.rewarded_at IS NOT NULL
          AND a.started_at >= now() - interval '48 hours'
          AND a.counted AND a.user_id IS NOT NULL AND a.kind <> 'game'
          AND EXISTS (
            SELECT 1 FROM media.playback_sessions p
            WHERE p.session_key LIKE '%:history:%'
              AND p.user_id = a.user_id
              AND p.state = 'stopped'
              AND p.object_id = a.object_id
              AND p.started_at <= coalesce(a.stopped_at, a.started_at) + interval '10 minutes'
              AND p.updated_at >= a.started_at - interval '10 minutes'
          )
        """
    )


def downgrade() -> None:
    pass  # nothing to undo: the plays looked at again keep what they gave
