"""media — the radio heard in sittings, counted when one ends (#259)

The radio counted its quarters of an hour as it went (#257): a gain every fifteen minutes, XP and Coins each
time. Like a film's minutes, it now counts once a sitting is over: ``radio_sittings`` keeps the seconds heard
in one (pauses included: the player opens a new stream to play on), and the sitting ends when nothing more
has been heard for a while — its minutes then make one ``media.radio_listened``.

``radio_listening`` (a day's total, its quarters already counted) goes: what it counted was given.

Revision ID: media_0015
Revises: media_0014
Create Date: 2026-10-27 17:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0015"
down_revision: str | Sequence[str] | None = "media_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.drop_table("radio_listening", schema="media")
    op.create_table(
        "radio_sittings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("seconds", sa.Float(), nullable=False),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.Column("ended_at", TZ, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_radio_sittings"),
        schema="media",
    )
    op.create_index("ix_radio_sittings_user", "radio_sittings", ["user_id", "updated_at"], schema="media")
    op.create_index(
        "ix_radio_sittings_open",
        "radio_sittings",
        ["updated_at"],
        schema="media",
        postgresql_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_radio_sittings_open", table_name="radio_sittings", schema="media")
    op.drop_index("ix_radio_sittings_user", table_name="radio_sittings", schema="media")
    op.drop_table("radio_sittings", schema="media")
    op.create_table(
        "radio_listening",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("seconds", sa.Float(), nullable=False),
        sa.Column("slices", sa.Integer(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("user_id", "day", name="pk_radio_listening"),
        schema="media",
    )
