"""search initial schema — extensions ``unaccent`` / ``pg_trgm`` (lexical matching), private search history,
index state, and the semantic ``embeddings`` table only when pgvector is available (spec 008 T008)

Revision ID: search_0001
Revises:
Create Date: 2026-10-04 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "search_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("search",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)

# pgvector is optional: semantic search degrades honestly when the extension is not installable (R3/R4)
EMBEDDINGS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE IF NOT EXISTS search.embeddings (
            kind varchar(96) NOT NULL,
            id varchar(128) NOT NULL,
            language varchar(35) NOT NULL DEFAULT '',
            embedding vector NOT NULL,
            content_hash varchar(64) NOT NULL,
            model_id varchar(128) NOT NULL,
            visibility_epoch bigint NOT NULL DEFAULT 0,
            indexed_at timestamptz NOT NULL,
            CONSTRAINT pk_embeddings PRIMARY KEY (kind, id, language)
        );
    END IF;
END
$$
"""


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "search"')
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("query_text", sa.String(512), nullable=False),
        sa.Column("normalized_query", sa.String(512), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("performed_at", TZ, nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_history"),
        sa.UniqueConstraint("user_id", "normalized_query", name="uq_history_user_query"),
        sa.CheckConstraint("mode IN ('exact', 'semantic', 'mixed')", name="ck_history_mode"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_history_user_id_users", ondelete="CASCADE"
        ),
        schema="search",
    )
    op.create_index("ix_history_user_performed", "history", ["user_id", "performed_at"], schema="search")
    op.create_table(
        "index_state",
        sa.Column("kind", sa.String(96), nullable=False),
        sa.Column("last_full_reindex_at", TZ),
        sa.Column("last_indexed_at", TZ),
        sa.Column("pending_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("embedding_model", sa.String(128)),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("kind", name="pk_index_state"),
        schema="search",
    )
    op.execute(EMBEDDINGS)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS search.embeddings")
    op.drop_table("index_state", schema="search")
    op.drop_index("ix_history_user_performed", table_name="history", schema="search")
    op.drop_table("history", schema="search")
