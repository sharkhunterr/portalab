"""media — who started a portal-player stream, and the household profile a live session was watched by
(spec 032)

Revision ID: media_0027
Revises: media_0026
Create Date: 2026-11-14 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0027"
down_revision: str | Sequence[str] | None = "media_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portal_streams",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("account", sa.String(200), nullable=True),
        sa.Column("item", sa.String(200), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portal_streams")),
        schema="media",
    )
    op.create_index(
        "ix_portal_streams_item", "portal_streams", ["service_id", "item", "started_at"], schema="media"
    )
    op.add_column("playback_sessions", sa.Column("played_by", sa.Uuid(), nullable=True), schema="media")


def downgrade() -> None:
    op.drop_column("playback_sessions", "played_by", schema="media")
    op.drop_index("ix_portal_streams_item", table_name="portal_streams", schema="media")
    op.drop_table("portal_streams", schema="media")
