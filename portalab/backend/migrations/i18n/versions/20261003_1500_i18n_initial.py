"""i18n initial schema — languages (seed en, fr), catalog overrides and versions, localized content
registry (source rows immutable), missing-key stats (spec 026 T008)

Revision ID: i18n_0001
Revises:
Create Date: 2026-10-03 15:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "i18n_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("i18n",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
NOW = datetime(2026, 10, 3, tzinfo=UTC)

SOURCE_IMMUTABLE = """
CREATE OR REPLACE FUNCTION i18n.protect_source_versions() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.state = 'source' THEN
        RAISE EXCEPTION 'source content versions are immutable (add a new version instead)' USING ERRCODE = 'P0001';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$
"""
SOURCE_TRIGGER = """
CREATE TRIGGER localized_content_source_immutable BEFORE UPDATE OR DELETE ON i18n.localized_content_versions
FOR EACH ROW EXECUTE FUNCTION i18n.protect_source_versions()
"""


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "i18n"')
    languages = op.create_table(
        "languages",
        sa.Column("code", sa.String(35), nullable=False),
        sa.Column("name_native", sa.String(80), nullable=False),
        sa.Column("name_en", sa.String(80), nullable=False),
        sa.Column("direction", sa.String(3), nullable=False),
        sa.Column("fallback_code", sa.String(35)),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("code", name="pk_languages"),
        sa.ForeignKeyConstraint(
            ["fallback_code"], ["i18n.languages.code"], name="fk_languages_fallback_code_languages"
        ),
        sa.CheckConstraint("direction IN ('ltr', 'rtl')", name="ck_languages_direction"),
        schema="i18n",
    )
    op.bulk_insert(
        languages,
        [
            {
                "code": "en",
                "name_native": "English",
                "name_en": "English",
                "direction": "ltr",
                "fallback_code": None,
                "source": "builtin",
                "created_at": NOW,
            },
            {
                "code": "fr",
                "name_native": "Français",
                "name_en": "French",
                "direction": "ltr",
                "fallback_code": "en",
                "source": "builtin",
                "created_at": NOW,
            },
        ],
    )
    op.create_table(
        "catalog_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("namespace", sa.String(64), nullable=False),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("language", sa.String(35), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Uuid()),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_entries"),
        sa.UniqueConstraint("namespace", "key", "language", name="uq_catalog_entries"),
        sa.ForeignKeyConstraint(
            ["language"], ["i18n.languages.code"], name="fk_catalog_entries_language_languages"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["identity.users.id"],
            name="fk_catalog_entries_updated_by_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("state IN ('draft', 'published', 'deprecated')", name="ck_catalog_entries_state"),
        schema="i18n",
    )
    op.create_table(
        "catalog_versions",
        sa.Column("namespace", sa.String(64), nullable=False),
        sa.Column("language", sa.String(35), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("published_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("namespace", "language", name="pk_catalog_versions"),
        schema="i18n",
    )
    op.create_table(
        "localized_content_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_kind", sa.String(64), nullable=False),
        sa.Column("content_id", sa.String(128), nullable=False),
        sa.Column("language", sa.String(35), nullable=False),
        sa.Column("source_language", sa.String(35), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("translation_of_version", sa.Integer()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_localized_content_versions"),
        sa.UniqueConstraint(
            "content_kind", "content_id", "language", "version", name="uq_localized_content_versions"
        ),
        sa.ForeignKeyConstraint(
            ["language"], ["i18n.languages.code"], name="fk_localized_content_versions_language_languages"
        ),
        sa.ForeignKeyConstraint(
            ["source_language"],
            ["i18n.languages.code"],
            name="fk_localized_content_versions_source_language_languages",
        ),
        sa.CheckConstraint(
            "state IN ('source', 'translated', 'untranslated', 'machine_draft')",
            name="ck_localized_content_versions_state",
        ),
        schema="i18n",
    )
    op.create_index(
        "ix_localized_content_lookup",
        "localized_content_versions",
        ["content_kind", "content_id", "language"],
        schema="i18n",
    )
    op.execute(SOURCE_IMMUTABLE)
    op.execute(SOURCE_TRIGGER)
    op.create_table(
        "missing_key_stats",
        sa.Column("namespace", sa.String(64), nullable=False),
        sa.Column("language", sa.String(35), nullable=False),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", TZ, nullable=False),
        sa.Column("last_seen_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("namespace", "language", "key", name="pk_missing_key_stats"),
        schema="i18n",
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS localized_content_source_immutable ON i18n.localized_content_versions")
    op.execute("DROP FUNCTION IF EXISTS i18n.protect_source_versions()")
    for table in (
        "missing_key_stats",
        "localized_content_versions",
        "catalog_versions",
        "catalog_entries",
        "languages",
    ):
        op.drop_table(table, schema="i18n")
    op.execute('DROP SCHEMA IF EXISTS "i18n"')
