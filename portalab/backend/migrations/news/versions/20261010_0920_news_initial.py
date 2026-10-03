"""news schema — categories, articles, append-only revisions, translations (spec 011 T009)

Revision ID: news_0001
Revises:
Create Date: 2026-10-10 09:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "news_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("news",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
# Revisions are append-only; only an erased author may be tombstoned (author_id -> NULL).
REVISION_GUARD = """
CREATE OR REPLACE FUNCTION news.protect_revisions() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'news.article_revisions is append-only';
    END IF;
    IF (NEW.article_id, NEW.version, NEW.title, NEW.summary, NEW.body_md, NEW.changed_at)
         IS DISTINCT FROM (OLD.article_id, OLD.version, OLD.title, OLD.summary, OLD.body_md, OLD.changed_at)
       OR (NEW.author_id IS DISTINCT FROM OLD.author_id AND NEW.author_id IS NOT NULL) THEN
        RAISE EXCEPTION 'news.article_revisions is append-only';
    END IF;
    RETURN NEW;
END $$
"""
REVISION_TRIGGER = """
CREATE TRIGGER article_revisions_append_only BEFORE UPDATE OR DELETE ON news.article_revisions
FOR EACH ROW EXECUTE FUNCTION news.protect_revisions()
"""
TABLES = ("article_translations", "article_revisions", "articles", "categories")


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "news"')
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint("key", name="uq_categories_key"),
        schema="news",
    )
    op.create_table(
        "articles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("rendered_html", sa.Text(), nullable=False),
        sa.Column("renderer_version", sa.String(length=8), nullable=False),
        sa.Column("plain_text", sa.Text(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("audience", postgresql.JSONB(), nullable=False),
        sa.Column("publish_at", TZ, nullable=True),
        sa.Column("published_at", TZ, nullable=True),
        sa.Column("archived_at", TZ, nullable=True),
        sa.Column("featured_from", TZ, nullable=True),
        sa.Column("featured_until", TZ, nullable=True),
        sa.Column("feature_priority", sa.Integer(), nullable=False),
        sa.Column("notify_on_publish", sa.Boolean(), nullable=False),
        sa.Column("publish_seq", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'scheduled', 'published', 'archived', 'deleted')", name="ck_articles_status"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["news.categories.id"], name="fk_articles_category_id_categories"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_articles"),
        sa.UniqueConstraint("slug", name="uq_articles_slug"),
        _user_fk("articles", "author_id", "SET NULL"),
        schema="news",
    )
    op.create_index(
        "ix_articles_published", "articles", ["status", "published_at"], unique=False, schema="news"
    )
    op.create_index(
        "ix_articles_search",
        "articles",
        ["search_vector"],
        unique=False,
        schema="news",
        postgresql_using="gin",
    )
    op.create_table(
        "article_revisions",
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("changed_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"], ["news.articles.id"], name="fk_article_revisions_article_id_articles"
        ),
        sa.PrimaryKeyConstraint("article_id", "version", name="pk_article_revisions"),
        schema="news",
    )
    op.create_table(
        "article_translations",
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("rendered_html", sa.Text(), nullable=False),
        sa.Column("renderer_version", sa.String(length=8), nullable=False),
        sa.Column("state", sa.String(length=14), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("state IN ('translated', 'machine_draft')", name="ck_article_translations_state"),
        sa.ForeignKeyConstraint(
            ["article_id"], ["news.articles.id"], name="fk_article_translations_article_id_articles"
        ),
        sa.PrimaryKeyConstraint("article_id", "language", name="pk_article_translations"),
        schema="news",
    )
    op.execute(REVISION_GUARD)
    op.execute(REVISION_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS article_revisions_append_only ON news.article_revisions")
    op.execute("DROP FUNCTION IF EXISTS news.protect_revisions()")
    for table in TABLES:
        op.drop_table(table, schema="news")
    op.execute('DROP SCHEMA IF EXISTS "news"')
