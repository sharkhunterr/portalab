"""news — a letter published in the news shows itself, as any news (#335)

``news.articles.edition_id``: the newsletter letter an article shows (its letter's page in place of a body);
the articles announcing a letter so far (#332) are linked to it by the link their body holds.

Revision ID: news_0011
Revises: news_0010
Create Date: 2026-11-02 14:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "news_0011"
down_revision: str | Sequence[str] | None = "news_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("edition_id", sa.Uuid(), nullable=True), schema="news")
    op.create_foreign_key(
        "fk_articles_edition_id_newsletter_editions",
        "articles",
        "newsletter_editions",
        ["edition_id"],
        ["id"],
        source_schema="news",
        referent_schema="news",
        ondelete="SET NULL",
    )
    op.execute(
        """
        UPDATE news.articles a SET edition_id = e.id
        FROM news.newsletter_editions e
        WHERE a.body_md LIKE '%(/news/editions/' || e.id::text || ')%'
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_articles_edition_id_newsletter_editions", "articles", schema="news")
    op.drop_column("articles", "edition_id", schema="news")
