"""connectors initial schema — services, capabilities, sync state/history, discovery, compatibility
(spec 005 T006)

Revision ID: connectors_0001
Revises:
Create Date: 2026-10-02 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "connectors_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("connectors",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001", "events_0001")

TZ = sa.DateTime(timezone=True)
STATES = (
    "'configured', 'enabled', 'syncing', 'error', 'unavailable', 'maintenance', 'disabled', 'disconnected'"
)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "connectors"')
    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connector_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("credentials", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("state_seq", sa.Integer(), nullable=False),
        sa.Column("state_reason", sa.String(256)),
        sa.Column("state_changed_at", TZ, nullable=False),
        sa.Column("enabled_at", TZ),
        sa.Column("disabled_at", TZ),
        sa.Column("disconnected_at", TZ),
        sa.Column("sync_interval_seconds", sa.Integer()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_services"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["identity.users.id"], name="fk_services_created_by_users", ondelete="SET NULL"
        ),
        sa.CheckConstraint(f"state IN ({STATES})", name="ck_services_state"),
        schema="connectors",
    )
    op.create_index("ix_services_connector_key", "services", ["connector_key"], schema="connectors")
    op.create_table(
        "service_capabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_service_capabilities"),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["connectors.services.id"],
            name="fk_service_capabilities_service_id_services",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("service_id", "capability", name="uq_service_capabilities"),
        schema="connectors",
    )
    op.create_table(
        "sync_state",
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("last_attempt_at", TZ),
        sa.Column("last_success_at", TZ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("cursor", postgresql.JSONB()),
        sa.Column("next_run_at", TZ),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("service_id", name="pk_sync_state"),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["connectors.services.id"],
            name="fk_sync_state_service_id_services",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("status IN ('idle', 'running', 'failed')", name="ck_sync_state_status"),
        schema="connectors",
    )
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(128)),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("triggered_by", sa.Uuid()),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("finished_at", TZ, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("added", sa.Integer(), nullable=False),
        sa.Column("modified", sa.Integer(), nullable=False),
        sa.Column("removed", sa.Integer(), nullable=False),
        sa.Column("ignored", sa.Integer(), nullable=False),
        sa.Column("errored", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("partial", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sync_runs"),
        sa.CheckConstraint(
            "kind IN ('scheduled', 'manual', 'resync_partial', 'resync_full')", name="ck_sync_runs_kind"
        ),
        sa.CheckConstraint("status IN ('succeeded', 'partial', 'failed')", name="ck_sync_runs_status"),
        schema="connectors",
    )
    op.create_index(
        "ix_sync_runs_service_started", "sync_runs", ["service_id", "started_at"], schema="connectors"
    )
    # immutable rows: UPDATE and TRUNCATE are rejected; DELETE is left to the 021 retention window
    for statement in append_only_ddl("connectors", "sync_runs"):
        op.execute(statement.replace("BEFORE UPDATE OR DELETE", "BEFORE UPDATE"))
    op.create_table(
        "discovery_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connector_key", sa.String(64), nullable=False),
        sa.Column("target", sa.String(512), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("found_at", TZ, nullable=False),
        sa.Column("service_id", sa.Uuid()),
        sa.PrimaryKeyConstraint("id", name="pk_discovery_candidates"),
        sa.UniqueConstraint("connector_key", "target", name="uq_discovery_candidates_target"),
        sa.CheckConstraint(
            "status IN ('candidate', 'confirmed', 'declined')", name="ck_discovery_candidates_status"
        ),
        schema="connectors",
    )
    op.create_table(
        "compatibility_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connector_key", sa.String(64), nullable=False),
        sa.Column("portal_version", sa.String(32), nullable=False),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False),
        sa.Column("checked_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_compatibility_checks"),
        sa.CheckConstraint(
            "result IN ('compatible', 'warning', 'incompatible')", name="ck_compatibility_checks_result"
        ),
        schema="connectors",
    )
    op.create_index(
        "ix_compatibility_checks_connector",
        "compatibility_checks",
        ["connector_key", "checked_at"],
        schema="connectors",
    )


def downgrade() -> None:
    for statement in drop_append_only_ddl("connectors", "sync_runs"):
        op.execute(statement)
    for table in (
        "compatibility_checks",
        "discovery_candidates",
        "sync_runs",
        "sync_state",
        "service_capabilities",
        "services",
    ):
        op.drop_table(table, schema="connectors")
    op.execute('DROP SCHEMA IF EXISTS "connectors"')
