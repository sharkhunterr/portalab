"""games — a week's challenge per kind: a game to play, a film to watch through, a book and an audiobook to
take some way (issue 265)

Revision ID: games_0002
Revises: games_0001
Create Date: 2026-10-28 18:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "games_0002"
down_revision: str | Sequence[str] | None = "games_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table, keys in (("challenges", ["week", "kind"]), ("challenge_done", ["week", "kind", "user_id"])):
        op.add_column(
            table, sa.Column("kind", sa.String(12), nullable=False, server_default="game"), schema="games"
        )
        op.alter_column(table, "kind", server_default=None, schema="games")
        op.drop_constraint(f"pk_{table}", table, type_="primary", schema="games")
        op.create_primary_key(f"pk_{table}", table, keys, schema="games")


def downgrade() -> None:
    for table, keys in (("challenges", ["week"]), ("challenge_done", ["week", "user_id"])):
        op.execute(f"DELETE FROM games.{table} WHERE kind <> 'game'")  # noqa: S608 — constant table names
        op.drop_constraint(f"pk_{table}", table, type_="primary", schema="games")
        op.create_primary_key(f"pk_{table}", table, keys, schema="games")
        op.drop_column(table, "kind", schema="games")
