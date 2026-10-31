"""news — sources of news from elsewhere and their items (#299)

``news.feeds``: the RSS/Atom sources the editors chose (cadence, words, channel, health);
``news.feed_items``: what they published lately — title, short summary, link, a copied picture, the library
titles and people each names; pinned or hidden by the editors.

Revision ID: news_0004
Revises: news_0003
Create Date: 2026-10-31 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "news_0004"
down_revision: str | Sequence[str] | None = "news_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "feeds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("site_url", sa.String(length=1000), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("include_words", JSONB, nullable=False),
        sa.Column("exclude_words", JSONB, nullable=False),
        sa.Column("refresh_minutes", sa.Integer(), nullable=False),
        sa.Column("next_run_at", TZ, nullable=True),
        sa.Column("last_run_at", TZ, nullable=True),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("etag", sa.String(length=200), nullable=True),
        sa.Column("modified", sa.String(length=80), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("status IN ('never', 'ok', 'error')", name="ck_feeds_status"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["news.categories.id"],
            name="fk_feeds_category_id_categories",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feeds"),
        sa.UniqueConstraint("url", name="uq_feeds_url"),
        schema="news",
    )
    op.create_index("ix_feeds_due", "feeds", ["enabled", "next_run_at"], schema="news")
    op.create_table(
        "feed_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("feed_id", sa.Uuid(), nullable=False),
        sa.Column("guid", sa.String(length=500), nullable=False),
        sa.Column("link", sa.String(length=1000), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False),
        sa.Column("image_key", sa.String(length=200), nullable=True),
        sa.Column("published_at", TZ, nullable=False),
        sa.Column("fetched_at", TZ, nullable=False),
        sa.Column("mentions", JSONB, nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["feed_id"], ["news.feeds.id"], name="fk_feed_items_feed_id_feeds", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feed_items"),
        sa.UniqueConstraint("feed_id", "guid", name="uq_feed_items_feed_id_guid"),
        schema="news",
    )
    op.create_index("ix_feed_items_published", "feed_items", ["published_at"], schema="news")
    op.create_index("ix_feed_items_feed", "feed_items", ["feed_id", "published_at"], schema="news")
    op.create_index(
        "ix_feed_items_mentions", "feed_items", ["mentions"], schema="news", postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_table("feed_items", schema="news")
    op.drop_index("ix_feeds_due", table_name="feeds", schema="news")
    op.drop_table("feeds", schema="news")
