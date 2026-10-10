"""news — who read what (#48)

One row per member and published article they opened (``read_at`` the first time); the editors see who
read an article, and members see a dot on the news they have not read yet. Personal data: deleted with
the member (cascade) and exported with their data.

Revision ID: news_0003
Revises: news_0002
Create Date: 2026-10-10 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "news_0003"
down_revision: str | Sequence[str] | None = "news_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "article_reads",
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("article_id", "user_id", name="pk_article_reads"),
        sa.ForeignKeyConstraint(
            ["article_id"], ["news.articles.id"], name="fk_article_reads_article", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_article_reads_user_id_users", ondelete="CASCADE"
        ),
        schema="news",
    )
    op.create_index("ix_article_reads_user", "article_reads", ["user_id"], schema="news")


def downgrade() -> None:
    op.drop_index("ix_article_reads_user", table_name="article_reads", schema="news")
    op.drop_table("article_reads", schema="news")
