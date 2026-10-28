"""media — games played in the history; no « seen » verdict (#190)

``media.activity`` takes games (``game``: RomM's play sessions and the games its account played). What a member
saw, read or played is the services' to tell: the ``seen`` verdict goes (its rows with it).

Revision ID: media_0017
Revises: media_0016
Create Date: 2026-10-28 15:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "media_0017"
down_revision: str | Sequence[str] | None = "media_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = "'movie', 'episode', 'live', 'track', 'book', 'audiobook', {}'other'"


def _check(table: str, name: str, condition: str) -> None:
    op.execute(f"ALTER TABLE media.{table} DROP CONSTRAINT {name}")
    op.execute(f"ALTER TABLE media.{table} ADD CONSTRAINT {name} CHECK ({condition})")


def _activity(kinds: str) -> None:
    _check("activity", "ck_activity_kind", f"kind IN ({kinds})")


def _taste(verdicts: str) -> None:
    _check("taste", "ck_taste_verdict", f"verdict IN ({verdicts})")


def upgrade() -> None:
    _activity(KINDS.format("'game', "))
    op.execute("DELETE FROM media.taste WHERE verdict = 'seen'")
    _taste("'like', 'dislike', 'later'")


def downgrade() -> None:
    op.execute("DELETE FROM media.activity WHERE kind = 'game'")
    _activity(KINDS.format(""))
    _taste("'like', 'dislike', 'seen', 'later'")
