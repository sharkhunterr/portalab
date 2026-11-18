"""media — when a title became available (#499)

A member may follow any title — a film, a book, a game… —, one not in the library yet among them: its arrival
is told in « My feed ». The catalog now keeps when the library last made each title available
(``available_at``); the titles available today take the day they were first seen.

Revision ID: media_0031
Revises: media_0030
Create Date: 2026-11-18 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0031"
down_revision: str | Sequence[str] | None = "media_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("objects", sa.Column("available_at", sa.DateTime(timezone=True)), schema="media")
    op.execute("UPDATE media.objects SET available_at = first_seen_at WHERE available")


def downgrade() -> None:
    op.drop_column("objects", "available_at", schema="media")
