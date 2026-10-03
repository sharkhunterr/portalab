"""wiki schema — pages, append-only revisions, tags, links, translations (spec 011 T009)

Revision ID: wiki_0001
Revises:
Create Date: 2026-10-10 09:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "wiki_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("wiki",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
# Revisions are append-only: only the derived render cache may be refreshed and an erased author
# tombstoned (author_id -> NULL); everything else, and DELETE, is refused.
REVISION_GUARD = """
CREATE OR REPLACE FUNCTION wiki.protect_revisions() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'wiki.revisions is append-only';
    END IF;
    IF (NEW.page_id, NEW.version, NEW.title, NEW.body_md, NEW.change_note, NEW.restored_from_version,
        NEW.created_at) IS DISTINCT FROM (OLD.page_id, OLD.version, OLD.title, OLD.body_md, OLD.change_note,
        OLD.restored_from_version, OLD.created_at)
       OR (NEW.author_id IS DISTINCT FROM OLD.author_id AND NEW.author_id IS NOT NULL) THEN
        RAISE EXCEPTION 'wiki.revisions is append-only';
    END IF;
    RETURN NEW;
END $$
"""
REVISION_TRIGGER = """
CREATE TRIGGER revisions_append_only BEFORE UPDATE OR DELETE ON wiki.revisions
FOR EACH ROW EXECUTE FUNCTION wiki.protect_revisions()
"""
TABLES = ("revisions", "page_translations", "page_tags", "page_links", "pages")


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "wiki"')
    op.create_table(
        "pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("audience", postgresql.JSONB(), nullable=False),
        sa.Column("readable_by_ai", sa.Boolean(), nullable=False),
        sa.Column("help_keys", postgresql.JSONB(), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published', 'archived', 'deleted')", name="ck_pages_status"),
        sa.ForeignKeyConstraint(["parent_id"], ["wiki.pages.id"], name="fk_pages_parent_id_pages"),
        sa.PrimaryKeyConstraint("id", name="pk_pages"),
        sa.UniqueConstraint("slug", name="uq_pages_slug"),
        _user_fk("pages", "created_by", "SET NULL"),
        schema="wiki",
    )
    op.create_index("ix_pages_parent", "pages", ["parent_id", "position"], unique=False, schema="wiki")
    op.create_index(
        "ix_pages_search", "pages", ["search_vector"], unique=False, schema="wiki", postgresql_using="gin"
    )
    op.create_table(
        "page_links",
        sa.Column("from_page_id", sa.Uuid(), nullable=False),
        sa.Column("target_ref", sa.String(length=260), nullable=False),
        sa.ForeignKeyConstraint(["from_page_id"], ["wiki.pages.id"], name="fk_page_links_from_page_id_pages"),
        sa.PrimaryKeyConstraint("from_page_id", "target_ref", name="pk_page_links"),
        schema="wiki",
    )
    op.create_index("ix_page_links_target", "page_links", ["target_ref"], unique=False, schema="wiki")
    op.create_table(
        "page_tags",
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("tag", sa.String(length=60), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["wiki.pages.id"], name="fk_page_tags_page_id_pages"),
        sa.PrimaryKeyConstraint("page_id", "tag", name="pk_page_tags"),
        schema="wiki",
    )
    op.create_index("ix_page_tags_tag", "page_tags", ["tag"], unique=False, schema="wiki")
    op.create_table(
        "page_translations",
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("rendered_html", sa.Text(), nullable=False),
        sa.Column("renderer_version", sa.String(length=8), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=14), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("state IN ('translated', 'machine_draft')", name="ck_page_translations_state"),
        sa.ForeignKeyConstraint(["page_id"], ["wiki.pages.id"], name="fk_page_translations_page_id_pages"),
        sa.PrimaryKeyConstraint("page_id", "language", name="pk_page_translations"),
        schema="wiki",
    )
    op.create_table(
        "revisions",
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("rendered_html", sa.Text(), nullable=False),
        sa.Column("renderer_version", sa.String(length=8), nullable=False),
        sa.Column("plain_text", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("change_note", sa.String(length=300), nullable=False),
        sa.Column("restored_from_version", sa.Integer(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["wiki.pages.id"], name="fk_revisions_page_id_pages"),
        sa.PrimaryKeyConstraint("page_id", "version", name="pk_revisions"),
        schema="wiki",
    )
    op.execute(REVISION_GUARD)
    op.execute(REVISION_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS revisions_append_only ON wiki.revisions")
    op.execute("DROP FUNCTION IF EXISTS wiki.protect_revisions()")
    for table in TABLES:
        op.drop_table(table, schema="wiki")
    op.execute('DROP SCHEMA IF EXISTS "wiki"')
