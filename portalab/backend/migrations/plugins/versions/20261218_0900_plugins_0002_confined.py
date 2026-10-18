"""plugins — confined plugins (spec 030): runtime, grants, attempts, network calls, secret settings, slot
settings, confirmations

Revision ID: plugins_0002
Revises: plugins_0001
Create Date: 2026-12-18 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "plugins_0002"
down_revision: str | Sequence[str] | None = "plugins_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)
OLD_STATES = (
    "installed", "needs_configuration", "enabled", "disabled", "update_pending", "update_failed",
    "incompatible", "quarantined", "archived",
)  # fmt: skip
STATES = (*OLD_STATES, "held_unconfined", "held_confinement")
ATTEMPTS = (
    "denied_capability", "denied_operation", "denied_host", "private_address", "oversize", "timeout",
    "unresponsive", "memory", "crash", "busy", "storage_quota", "rate", "confinement", "denied_statement",
)  # fmt: skip


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.add_column(
        "plugins",
        sa.Column("runtime", sa.String(length=12), nullable=False, server_default="declarative"),
        schema="plugins",
    )
    op.add_column("plugins", sa.Column("confinement", postgresql.JSONB(), nullable=True), schema="plugins")
    op.add_column(
        "plugins",
        sa.Column("predates_confinement", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="plugins",
    )
    # what is installed now keeps running as it does: in-process code stays allowed for these plugins
    op.execute(
        "UPDATE plugins.plugins p SET runtime = 'in_process', predates_confinement = true "
        "FROM plugins.versions v WHERE v.plugin_key = p.key AND v.version = p.current_version "
        "AND v.manifest ? 'entry_point'"
    )
    op.alter_column("plugins", "runtime", server_default=None, schema="plugins")
    op.alter_column("plugins", "predates_confinement", server_default=None, schema="plugins")
    op.create_check_constraint(
        "ck_plugins_runtime",
        "plugins",
        f"runtime IN ({_in(('declarative', 'in_process', 'confined'))})",
        schema="plugins",
    )
    op.drop_constraint("ck_plugins_state", "plugins", schema="plugins")
    op.create_check_constraint("ck_plugins_state", "plugins", f"state IN ({_in(STATES)})", schema="plugins")

    op.create_table(
        "grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plugin_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("capability", sa.String(length=24), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("granted_by", sa.Uuid(), nullable=True),
        sa.Column("granted_at", TZ, nullable=False),
        sa.Column("revoked_at", TZ, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_grants"),
        sa.UniqueConstraint(
            "plugin_key", "version", "capability", name="uq_grants_plugin_key_version_capability"
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"], ["identity.users.id"], name="fk_grants_granted_by_users", ondelete="SET NULL"
        ),
        schema="plugins",
    )
    op.create_table(
        "attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plugin_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.CheckConstraint(f"kind IN ({_in(ATTEMPTS)})", name="ck_attempts_kind"),
        sa.PrimaryKeyConstraint("id", name="pk_attempts"),
        schema="plugins",
    )
    op.create_index("ix_attempts_plugin", "attempts", ["plugin_key", "occurred_at"], schema="plugins")
    for statement in append_only_ddl("plugins", "attempts"):
        op.execute(statement)
    op.create_table(
        "network_calls",
        sa.Column("plugin_key", sa.String(length=64), nullable=False),
        sa.Column("host", sa.String(length=253), nullable=False),
        sa.Column("hour", TZ, nullable=False),
        sa.Column("calls", sa.BigInteger(), nullable=False),
        sa.Column("refused", sa.BigInteger(), nullable=False),
        sa.Column("bytes_in", sa.BigInteger(), nullable=False),
        sa.Column("bytes_out", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("plugin_key", "host", "hour", name="pk_network_calls"),
        schema="plugins",
    )
    op.create_table(
        "secret_settings",
        sa.Column("plugin_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=48), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("plugin_key", "name", name="pk_secret_settings"),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["identity.users.id"],
            name="fk_secret_settings_updated_by_users",
            ondelete="SET NULL",
        ),
        schema="plugins",
    )
    op.create_table(
        "slot_settings",
        sa.Column("slot", sa.String(length=32), nullable=False),
        sa.Column("contribution", sa.String(length=160), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("slot", "contribution", name="pk_slot_settings"),
        schema="plugins",
    )
    op.create_table(
        "confirmations",
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plugin_key", sa.String(length=64), nullable=False),
        sa.Column("route", sa.String(length=140), nullable=False),
        sa.Column("body_hash", sa.LargeBinary(), nullable=False),
        sa.Column("summary", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("used_at", TZ, nullable=True),
        sa.PrimaryKeyConstraint("token_hash", name="pk_confirmations"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_confirmations_user_id_users", ondelete="CASCADE"
        ),
        schema="plugins",
    )


def downgrade() -> None:
    op.drop_table("confirmations", schema="plugins")
    op.drop_table("slot_settings", schema="plugins")
    op.drop_table("secret_settings", schema="plugins")
    op.drop_table("network_calls", schema="plugins")
    for statement in drop_append_only_ddl("plugins", "attempts"):
        op.execute(statement)
    op.drop_index("ix_attempts_plugin", "attempts", schema="plugins")
    op.drop_table("attempts", schema="plugins")
    op.drop_table("grants", schema="plugins")
    op.execute(
        "UPDATE plugins.plugins SET state = 'disabled' WHERE state IN ('held_unconfined', 'held_confinement')"
    )
    op.drop_constraint("ck_plugins_state", "plugins", schema="plugins")
    op.create_check_constraint(
        "ck_plugins_state", "plugins", f"state IN ({_in(OLD_STATES)})", schema="plugins"
    )
    op.drop_constraint("ck_plugins_runtime", "plugins", schema="plugins")
    op.drop_column("plugins", "predates_confinement", schema="plugins")
    op.drop_column("plugins", "confinement", schema="plugins")
    op.drop_column("plugins", "runtime", schema="plugins")
