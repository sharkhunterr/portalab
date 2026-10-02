"""observability initial schema ``obs`` — component health, history, metric samples, rollups, errors,
anomalies, contributions (spec 025 T007)

Revision ID: observability_0001
Revises:
Create Date: 2026-10-02 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "observability_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("observability",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001", "health_0001")

TZ = sa.DateTime(timezone=True)

PARTITIONS = """
DO $$
DECLARE
    month date;
BEGIN
    EXECUTE 'CREATE TABLE obs.metric_samples_pdefault PARTITION OF obs.metric_samples DEFAULT';
    month := date_trunc('month', now())::date;
    WHILE month <= (date_trunc('month', now()) + interval '2 months')::date LOOP
        EXECUTE format(
            'CREATE TABLE obs.%I PARTITION OF obs.metric_samples FOR VALUES FROM (%L) TO (%L)',
            'metric_samples_p' || to_char(month, 'YYYYMM'), month, (month + interval '1 month')::date
        );
        month := (month + interval '1 month')::date;
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "obs"')
    op.create_table(
        "component_health",
        sa.Column("component", sa.String(128), nullable=False),
        sa.Column("owner", sa.String(128), nullable=False),
        sa.Column("technical", sa.String(16), nullable=False),
        sa.Column("functional", sa.String(16), nullable=False),
        sa.Column("since", TZ, nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("reason", postgresql.JSONB(), nullable=False),
        sa.Column("evaluated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("component", name="pk_component_health"),
        sa.CheckConstraint(
            "technical IN ('ok', 'degraded', 'down', 'unknown')", name="ck_component_health_technical"
        ),
        sa.CheckConstraint(
            "functional IN ('ok', 'degraded', 'failing', 'unknown')", name="ck_component_health_functional"
        ),
        schema="obs",
    )
    op.create_table(
        "health_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("component", sa.String(128), nullable=False),
        sa.Column("axis", sa.String(16), nullable=False),
        sa.Column("from_state", sa.String(16)),
        sa.Column("to_state", sa.String(16), nullable=False),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.Column("reason", sa.String(256), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_health_history"),
        sa.CheckConstraint("axis IN ('technical', 'functional')", name="ck_health_history_axis"),
        schema="obs",
    )
    op.create_index(
        "ix_health_history_component_occurred", "health_history", ["component", "occurred_at"], schema="obs"
    )
    for statement in append_only_ddl("obs", "health_history"):
        op.execute(statement)
    op.execute(
        """
        CREATE TABLE obs.metric_samples (
            id uuid NOT NULL,
            sampled_at timestamptz NOT NULL,
            component varchar(128) NOT NULL,
            metric varchar(128) NOT NULL,
            labels jsonb NOT NULL,
            kind varchar(16) NOT NULL,
            count integer NOT NULL,
            sum double precision NOT NULL,
            max double precision,
            p95 double precision,
            CONSTRAINT pk_metric_samples PRIMARY KEY (id, sampled_at)
        ) PARTITION BY RANGE (sampled_at)
        """
    )
    op.create_index(
        "ix_metric_samples_metric", "metric_samples", ["component", "metric", "sampled_at"], schema="obs"
    )
    op.execute(PARTITIONS)
    op.create_table(
        "rollups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("component", sa.String(128), nullable=False),
        sa.Column("metric", sa.String(128), nullable=False),
        sa.Column("labels", postgresql.JSONB(), nullable=False),
        sa.Column("labels_key", sa.String(512), nullable=False),
        sa.Column("bucket_kind", sa.String(8), nullable=False),
        sa.Column("bucket", TZ, nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("sum", sa.Float(), nullable=False),
        sa.Column("p95", sa.Float()),
        sa.Column("max", sa.Float()),
        sa.PrimaryKeyConstraint("id", name="pk_rollups"),
        sa.UniqueConstraint(
            "component", "metric", "labels_key", "bucket_kind", "bucket", name="uq_rollups_bucket"
        ),
        sa.CheckConstraint("bucket_kind IN ('hour', 'day')", name="ck_rollups_bucket_kind"),
        schema="obs",
    )
    op.create_table(
        "errors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("component", sa.String(128), nullable=False),
        sa.Column("service_ref", sa.String(64)),
        sa.Column("plugin_ref", sa.String(128)),
        sa.Column("event_ref", sa.String(64)),
        sa.Column("user_ref", sa.Uuid()),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("error_type", sa.String(128), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", TZ, nullable=False),
        sa.Column("last_seen_at", TZ, nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("resolution", sa.Text()),
        sa.Column("resolved_by", sa.Uuid()),
        sa.Column("resolved_at", TZ),
        sa.PrimaryKeyConstraint("id", name="pk_errors"),
        sa.UniqueConstraint("fingerprint", name="uq_errors_fingerprint"),
        sa.ForeignKeyConstraint(
            ["user_ref"], ["identity.users.id"], name="fk_errors_user_ref_users", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["identity.users.id"], name="fk_errors_resolved_by_users", ondelete="SET NULL"
        ),
        sa.CheckConstraint("state IN ('open', 'acknowledged', 'resolved')", name="ck_errors_state"),
        schema="obs",
    )
    op.create_index("ix_errors_state_last_seen", "errors", ["state", "last_seen_at"], schema="obs")
    op.create_table(
        "anomalies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("detector", sa.String(64), nullable=False),
        sa.Column("component", sa.String(128), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("detected_at", TZ, nullable=False),
        sa.Column("last_seen_at", TZ, nullable=False),
        sa.Column("occurrences", sa.Integer(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("incident_ref", sa.String(64)),
        sa.Column("validated_by", sa.Uuid()),
        sa.Column("escalation_attempts", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_anomalies"),
        sa.ForeignKeyConstraint(
            ["validated_by"],
            ["identity.users.id"],
            name="fk_anomalies_validated_by_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('candidate', 'pending_validation', 'escalated', 'dismissed', 'resolved')",
            name="ck_anomalies_status",
        ),
        sa.CheckConstraint("severity IN ('info', 'warning', 'critical')", name="ck_anomalies_severity"),
        schema="obs",
    )
    op.create_index("ix_anomalies_fingerprint_status", "anomalies", ["fingerprint", "status"], schema="obs")
    op.create_table(
        "contributions",
        sa.Column("contribution_id", sa.String(128), nullable=False),
        sa.Column("owner", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("declared_at", TZ, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("contribution_id", name="pk_contributions"),
        schema="obs",
    )


def downgrade() -> None:
    for statement in drop_append_only_ddl("obs", "health_history"):
        op.execute(statement)
    for table in (
        "contributions",
        "anomalies",
        "errors",
        "rollups",
        "metric_samples",
        "health_history",
        "component_health",
    ):
        op.execute(f'DROP TABLE IF EXISTS "obs"."{table}" CASCADE')
    op.execute('DROP SCHEMA IF EXISTS "obs"')
