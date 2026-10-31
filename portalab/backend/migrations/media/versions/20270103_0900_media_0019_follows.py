"""media — what each member follows, and when they last read their feed (#299)

``media.follows``: the people, titles and genres a member follows for « Mon fil » (private);
``media.feed_seen``: when they last opened it, so what arrived since is counted as unread.

Revision ID: media_0019
Revises: media_0018
Create Date: 2026-10-31 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0019"
down_revision: str | Sequence[str] | None = "media_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "follows",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("ref", sa.String(length=200), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint("kind IN ('person', 'title', 'genre')", name="ck_follows_kind"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_follows_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "kind", "ref", name="pk_follows"),
        schema="media",
    )
    op.create_index("ix_follows_user", "follows", ["user_id", "created_at"], schema="media")
    op.create_table(
        "feed_seen",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("seen_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_feed_seen_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_feed_seen"),
        schema="media",
    )
    # what arrived lately: the feed reads the library by first sight
    op.create_index("ix_objects_first_seen", "objects", ["first_seen_at"], schema="media")


def downgrade() -> None:
    op.drop_index("ix_objects_first_seen", table_name="objects", schema="media")
    op.drop_table("feed_seen", schema="media")
    op.drop_index("ix_follows_user", table_name="follows", schema="media")
    op.drop_table("follows", schema="media")
