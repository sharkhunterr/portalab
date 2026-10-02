"""administration initial schema — config store, policies, history, toggles, first run (spec 020 T006)

Revision ID: administration_0001
Revises:
Create Date: 2026-10-02 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "administration_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("administration",)
depends_on: str | Sequence[str] | None = ("core_0003",)

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "config"')
    op.execute('CREATE SCHEMA IF NOT EXISTS "admin"')
    op.create_table(
        "settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("scope", sa.String(8), nullable=False),
        sa.Column("scope_ref", sa.String(64), nullable=False),
        sa.Column("value", postgresql.JSONB()),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Uuid()),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_settings"),
        sa.UniqueConstraint("key", "scope", "scope_ref", name="uq_settings_key_scope"),
        sa.CheckConstraint("scope IN ('global', 'module', 'plugin', 'user')", name="ck_settings_scope"),
        schema="config",
    )
    op.create_index("ix_settings_scope_ref", "settings", ["scope", "scope_ref"], schema="config")
    op.create_table(
        "policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("bounds", postgresql.JSONB()),
        sa.Column("set_by", sa.Uuid()),
        sa.Column("set_at", TZ, nullable=False),
        sa.Column("removed_at", TZ),
        sa.PrimaryKeyConstraint("id", name="pk_policies"),
        sa.CheckConstraint("mode IN ('default', 'lock', 'bound')", name="ck_policies_mode"),
        schema="config",
    )
    op.create_index(
        "uq_policies_active_key",
        "policies",
        ["key"],
        unique=True,
        schema="config",
        postgresql_where=sa.text("removed_at IS NULL"),
    )
    op.create_table(
        "setting_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("scope", sa.String(8), nullable=False),
        sa.Column("scope_ref_hash", sa.String(64), nullable=False),
        sa.Column("old_value_redacted", postgresql.JSONB()),
        sa.Column("new_value_redacted", postgresql.JSONB()),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("changed_at", TZ, nullable=False),
        sa.Column("reason", sa.String(256), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_setting_history"),
        schema="config",
    )
    op.create_index(
        "ix_setting_history_key_changed_at", "setting_history", ["key", "changed_at"], schema="config"
    )
    for statement in append_only_ddl("config", "setting_history"):
        op.execute(statement)
    op.create_table(
        "extension_toggles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("ref", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("changed_by", sa.Uuid()),
        sa.Column("changed_at", TZ, nullable=False),
        sa.Column("reason", sa.String(256), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_extension_toggles"),
        sa.UniqueConstraint("kind", "ref", name="uq_extension_toggles_kind_ref"),
        sa.CheckConstraint(
            "kind IN ('module', 'plugin', 'connector', 'service', 'automation')",
            name="ck_extension_toggles_kind",
        ),
        schema="admin",
    )
    op.create_table(
        "first_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("completed_at", TZ),
        sa.Column("completed_by", sa.Uuid()),
        sa.PrimaryKeyConstraint("id", name="pk_first_run"),
        sa.CheckConstraint("id = 1", name="ck_first_run_single_row"),
        schema="admin",
    )
    op.execute("INSERT INTO admin.first_run (id) VALUES (1)")


def downgrade() -> None:
    for statement in drop_append_only_ddl("config", "setting_history"):
        op.execute(statement)
    for table, schema in (
        ("first_run", "admin"),
        ("extension_toggles", "admin"),
        ("setting_history", "config"),
        ("policies", "config"),
        ("settings", "config"),
    ):
        op.drop_table(table, schema=schema)
    op.execute('DROP SCHEMA IF EXISTS "admin"')
    op.execute('DROP SCHEMA IF EXISTS "config"')
