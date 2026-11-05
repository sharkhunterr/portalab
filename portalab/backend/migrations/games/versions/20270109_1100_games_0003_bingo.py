"""games — the month's media bingo: its card, and the lines and full cards each member completed (issue 356)

Revision ID: games_0003
Revises: games_0002
Create Date: 2027-01-09 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "games_0003"
down_revision: str | Sequence[str] | None = "games_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "bingo_cards",
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("cells", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("month", name="pk_bingo_cards"),
        schema="games",
    )
    op.create_table(
        "bingo_done",
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("line", sa.String(8), nullable=False),
        sa.Column("at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("month", "user_id", "line", name="pk_bingo_done"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_bingo_done_user_id", ondelete="CASCADE"
        ),
        schema="games",
    )


def downgrade() -> None:
    op.drop_table("bingo_done", schema="games")
    op.drop_table("bingo_cards", schema="games")
