"""media — the radio in the history (#283)

``media.activity`` takes the radio (``radio``: a member's sittings at the station's stream, counted by the
server), so the statistics show it like the rest.

Revision ID: media_0018
Revises: media_0017
Create Date: 2026-10-30 10:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "media_0018"
down_revision: str | Sequence[str] | None = "media_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = "'movie', 'episode', 'live', 'track', 'book', 'audiobook', 'game', {}'other'"


def _activity(kinds: str) -> None:
    op.execute("ALTER TABLE media.activity DROP CONSTRAINT ck_activity_kind")
    op.execute(f"ALTER TABLE media.activity ADD CONSTRAINT ck_activity_kind CHECK (kind IN ({kinds}))")


def upgrade() -> None:
    _activity(KINDS.format("'radio', "))


def downgrade() -> None:
    op.execute("DELETE FROM media.activity WHERE kind = 'radio'")
    _activity(KINDS.format(""))
