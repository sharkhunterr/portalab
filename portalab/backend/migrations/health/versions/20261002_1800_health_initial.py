"""health initial schema — service state, history, samples, rollups, errors, maintenance, infra, incident
links (spec 006 T006)

Revision ID: health_0001
Revises:
Create Date: 2026-10-02 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "health_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("health",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001", "connectors_0001")

TZ = sa.DateTime(timezone=True)
STATES = "'operational', 'degraded', 'unavailable', 'maintenance', 'unknown'"


PARTITIONS = """
DO $$
DECLARE
    tbl text;
    month date;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['health_samples', 'infra_samples'] LOOP
        EXECUTE format('CREATE TABLE health.%I PARTITION OF health.%I DEFAULT', tbl || '_pdefault', tbl);
        month := date_trunc('month', now())::date;
        WHILE month <= (date_trunc('month', now()) + interval '2 months')::date LOOP
            EXECUTE format(
                'CREATE TABLE health.%I PARTITION OF health.%I FOR VALUES FROM (%L) TO (%L)',
                tbl || '_p' || to_char(month, 'YYYYMM'), tbl, month, (month + interval '1 month')::date
            );
            month := (month + interval '1 month')::date;
        END LOOP;
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "health"')
    op.create_table(
        "service_state",
        sa.Column("service_id", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("state_since", TZ, nullable=False),
        sa.Column("state_seq", sa.Integer(), nullable=False),
        sa.Column("last_check_at", TZ),
        sa.Column("last_ok_at", TZ),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("maintenance_id", sa.Uuid()),
        sa.Column("rules_version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("service_id", name="pk_service_state"),
        sa.CheckConstraint(f"state IN ({STATES})", name="ck_service_state_state"),
        schema="health",
    )
    op.create_table(
        "state_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.String(64), nullable=False),
        sa.Column("from_state", sa.String(16)),
        sa.Column("to_state", sa.String(16), nullable=False),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.Column("received_at", TZ, nullable=False),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_state_history"),
        schema="health",
    )
    op.create_index(
        "ix_state_history_service_occurred", "state_history", ["service_id", "occurred_at"], schema="health"
    )
    for statement in append_only_ddl("health", "state_history"):
        op.execute(statement)
    op.execute(
        """
        CREATE TABLE health.health_samples (
            id uuid NOT NULL,
            checked_at timestamptz NOT NULL,
            service_id varchar(64) NOT NULL,
            ok boolean NOT NULL,
            latency_ms double precision,
            error_code varchar(64),
            detail jsonb,
            CONSTRAINT pk_health_samples PRIMARY KEY (id, checked_at)
        ) PARTITION BY RANGE (checked_at)
        """
    )
    op.create_index(
        "ix_health_samples_service_checked", "health_samples", ["service_id", "checked_at"], schema="health"
    )
    op.execute(
        """
        CREATE TABLE health.infra_samples (
            id uuid NOT NULL,
            sampled_at timestamptz NOT NULL,
            service_id varchar(64) NOT NULL,
            metric varchar(32) NOT NULL,
            value double precision,
            unit varchar(16),
            available boolean NOT NULL,
            CONSTRAINT pk_infra_samples PRIMARY KEY (id, sampled_at)
        ) PARTITION BY RANGE (sampled_at)
        """
    )
    op.create_index(
        "ix_infra_samples_service_metric",
        "infra_samples",
        ["service_id", "metric", "sampled_at"],
        schema="health",
    )
    op.execute(PARTITIONS)
    op.create_table(
        "health_rollups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.String(64), nullable=False),
        sa.Column("bucket_start", TZ, nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False),
        sa.Column("ok_samples", sa.Integer(), nullable=False),
        sa.Column("p95_latency_ms", sa.Float()),
        sa.Column("downtime_seconds", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_health_rollups"),
        sa.UniqueConstraint("service_id", "bucket_start", name="uq_health_rollups_bucket"),
        schema="health",
    )
    op.create_table(
        "recent_errors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.String(64), nullable=False),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_recent_errors"),
        sa.UniqueConstraint("service_id", "code", name="uq_recent_errors_code"),
        schema="health",
    )
    op.create_table(
        "maintenance_windows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.String(64)),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("starts_at", TZ, nullable=False),
        sa.Column("ends_at", TZ, nullable=False),
        sa.Column("reference_time_zone", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("schedule_version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("cancelled_at", TZ),
        sa.PrimaryKeyConstraint("id", name="pk_maintenance_windows"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.users.id"],
            name="fk_maintenance_windows_created_by_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'active', 'ended', 'cancelled')", name="ck_maintenance_windows_status"
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_maintenance_windows_ordered"),
        schema="health",
    )
    op.create_index(
        "ix_maintenance_windows_service", "maintenance_windows", ["service_id", "starts_at"], schema="health"
    )
    op.create_table(
        "service_incident_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.String(64), nullable=False),
        sa.Column("incident_id", sa.String(64), nullable=False),
        sa.Column("linked_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_service_incident_links"),
        sa.UniqueConstraint("service_id", "incident_id", name="uq_service_incident_links"),
        schema="health",
    )


def downgrade() -> None:
    for statement in drop_append_only_ddl("health", "state_history"):
        op.execute(statement)
    for table in (
        "service_incident_links",
        "maintenance_windows",
        "recent_errors",
        "health_rollups",
        "infra_samples",
        "health_samples",
        "state_history",
        "service_state",
    ):
        op.execute(f'DROP TABLE IF EXISTS "health"."{table}" CASCADE')
    op.execute('DROP SCHEMA IF EXISTS "health"')
