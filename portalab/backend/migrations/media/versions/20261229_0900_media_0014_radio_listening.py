"""media — the radio's listening counted across streams, by member and day (#257)

The player closes the stream at each pause and opens a new one to play on: counting the quarters of an hour
inside one stream lost every minute short of fifteen. ``radio_listening`` keeps, for a member and a day (UTC),
the seconds the stream was relayed to them in all and the slices of a quarter of an hour already counted.

Revision ID: media_0014
Revises: media_0013
Create Date: 2026-10-27 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0014"
down_revision: str | Sequence[str] | None = "media_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "radio_listening",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("seconds", sa.Float(), nullable=False),
        sa.Column("slices", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "day", name="pk_radio_listening"),
        schema="media",
    )


def downgrade() -> None:
    op.drop_table("radio_listening", schema="media")
