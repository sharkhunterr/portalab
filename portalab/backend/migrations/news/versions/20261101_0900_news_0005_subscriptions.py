"""news — members' own sources (#299)

``news.feeds.editorial``: the editors' sources (on « À la une ») apart from members' own;
``news.feed_subscriptions``: who follows which source for their « Mon fil » (private).

Revision ID: news_0005
Revises: news_0004
Create Date: 2026-11-01 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "news_0005"
down_revision: str | Sequence[str] | None = "news_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feeds", sa.Column("editorial", sa.Boolean(), nullable=False, server_default="true"), schema="news"
    )
    op.create_table(
        "feed_subscriptions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("feed_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_feed_subscriptions_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["feed_id"], ["news.feeds.id"], name="fk_feed_subscriptions_feed_id_feeds", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "feed_id", name="pk_feed_subscriptions"),
        schema="news",
    )
    op.create_index("ix_feed_subscriptions_feed", "feed_subscriptions", ["feed_id"], schema="news")


def downgrade() -> None:
    op.drop_table("feed_subscriptions", schema="news")
    op.execute("DELETE FROM news.feeds WHERE NOT editorial")
    op.drop_column("feeds", "editorial", schema="news")
