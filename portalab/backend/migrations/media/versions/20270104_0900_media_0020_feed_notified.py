"""media — when a member was last told about « Mon fil » (#299)

``media.feed_notified``: the moment of the last notice, so the same arrivals are never notified twice.

Revision ID: media_0020
Revises: media_0019
Create Date: 2026-11-01 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0020"
down_revision: str | Sequence[str] | None = "media_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feed_notified",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_feed_notified_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_feed_notified"),
        schema="media",
    )


def downgrade() -> None:
    op.drop_table("feed_notified", schema="media")
