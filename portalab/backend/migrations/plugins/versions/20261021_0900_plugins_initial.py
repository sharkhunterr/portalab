"""plugins schema — plugins, versions, contributions, reviews, error stats, purges, update runs

Revision ID: plugins_0001
Revises:
Create Date: 2026-10-21 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "plugins_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("plugins",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
TABLES = (
    "versions",
    "version_states",
    "update_runs",
    "reviews",
    "purges",
    "plugins",
    "error_stats",
    "contributions",
)


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "plugins"')
    op.create_table(
        "contributions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plugin_key", sa.String(length=64), nullable=False),
        sa.Column("point", sa.String(length=32), nullable=False),
        sa.Column("contribution_id", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=8), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("detail", sa.String(length=300), nullable=True),
        sa.Column("registered_at", TZ, nullable=False),
        sa.Column("removed_at", TZ, nullable=True),
        sa.CheckConstraint("state IN ('active', 'removed', 'conflict')", name="ck_contributions_state"),
        sa.PrimaryKeyConstraint("id", name="pk_contributions"),
        schema="plugins",
    )
    op.create_index(
        "ix_contributions_plugin", "contributions", ["plugin_key", "state"], unique=False, schema="plugins"
    )
    op.create_table(
        "error_stats",
        sa.Column("plugin_key", sa.String(length=64), nullable=False),
        sa.Column("window_start", TZ, nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("last_sample", sa.String(length=300), nullable=True),
        sa.CheckConstraint(
            "kind IN ('route', 'event', 'action', 'widget', 'job', 'load', 'hook')",
            name="ck_error_stats_kind",
        ),
        sa.PrimaryKeyConstraint("plugin_key", "window_start", "kind", name="pk_error_stats"),
        schema="plugins",
    )
    op.create_table(
        "plugins",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("scope", sa.String(length=8), nullable=False),
        sa.Column("maturity", sa.String(length=12), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("current_version", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("needs_restart", sa.Boolean(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("installed_by", sa.Uuid(), nullable=True),
        sa.Column("installed_at", TZ, nullable=False),
        sa.Column("enabled_at", TZ, nullable=True),
        sa.Column("quarantine_reason", sa.String(length=300), nullable=True),
        sa.Column("last_error_at", TZ, nullable=True),
        sa.Column("state_seq", sa.Integer(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("scope IN ('portal', 'user')", name="ck_plugins_scope"),
        sa.CheckConstraint(
            "source IN ('admin_upload', 'local_dir', 'marketplace')", name="ck_plugins_source"
        ),
        sa.CheckConstraint(
            "state IN ('installed', 'needs_configuration', 'enabled', 'disabled', 'update_pending', 'update_failed', 'incompatible', 'quarantined', 'archived')",
            name="ck_plugins_state",
        ),
        sa.PrimaryKeyConstraint("key", name="pk_plugins"),
        _user_fk("plugins", "installed_by", "SET NULL"),
        schema="plugins",
    )
    op.create_table(
        "purges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plugin_key", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("exported", sa.Boolean(), nullable=False),
        sa.Column("export_ref", sa.String(length=500), nullable=True),
        sa.Column("executed_at", TZ, nullable=False),
        sa.Column("schema_dropped", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_purges"),
        schema="plugins",
        info={"portalab_append_only": True},
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plugin_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", TZ, nullable=False),
        sa.Column("permissions", postgresql.JSONB(), nullable=False),
        sa.Column("extension_points", postgresql.JSONB(), nullable=False),
        sa.Column("events", postgresql.JSONB(), nullable=False),
        sa.Column("personal_data", sa.Boolean(), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_reviews"),
        _user_fk("reviews", "approved_by", "SET NULL"),
        schema="plugins",
    )
    op.create_table(
        "update_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plugin_key", sa.String(length=64), nullable=False),
        sa.Column("from_version", sa.String(length=64), nullable=False),
        sa.Column("to_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("probation_until", TZ, nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint(
            "status IN ('staged', 'migrated', 'pending_restart', 'probation', 'succeeded', 'rolled_back', 'failed')",
            name="ck_update_runs_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_update_runs"),
        schema="plugins",
    )
    op.create_table(
        "version_states",
        sa.Column("plugin_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("probation_until", TZ, nullable=True),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("plugin_key", "version", name="pk_version_states"),
        schema="plugins",
    )
    op.create_table(
        "versions",
        sa.Column("plugin_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("package_path", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("installed_at", TZ, nullable=False),
        sa.CheckConstraint(
            "status IN ('current', 'previous', 'staged', 'failed', 'probation')", name="ck_versions_status"
        ),
        sa.ForeignKeyConstraint(
            ["plugin_key"], ["plugins.plugins.key"], name="fk_versions_plugin_key_plugins"
        ),
        sa.PrimaryKeyConstraint("plugin_key", "version", name="pk_versions"),
        schema="plugins",
        info={"portalab_append_only": True},
    )
    for table in ("versions", "purges"):
        for statement in append_only_ddl("plugins", table):
            op.execute(statement)


def downgrade() -> None:
    for table in ("versions", "purges"):
        for statement in drop_append_only_ddl("plugins", table):
            op.execute(statement)
    for table in TABLES:
        op.drop_table(table, schema="plugins")
    op.execute('DROP SCHEMA IF EXISTS "plugins"')
