"""events initial schema — partitioned history, dedup keys, quarantine, consumers, replay (spec 007 T006)
plus ``audit.audit_entries.event_id`` correlation (T026)

Revision ID: events_0001
Revises:
Create Date: 2026-10-02 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "events_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("events",)
depends_on: str | Sequence[str] | None = ("core_0003", "audit_0002")

TZ = sa.DateTime(timezone=True)

CREATE_EVENTS = """
CREATE TABLE events.events (
    event_id uuid NOT NULL,
    retention_class varchar(16) NOT NULL,
    occurred_at timestamptz NOT NULL,
    seq bigint GENERATED ALWAYS AS IDENTITY,
    type varchar(128) NOT NULL,
    type_version integer NOT NULL,
    received_at timestamptz NOT NULL,
    source_system varchar(128) NOT NULL,
    source_event_id varchar(256),
    source_ref jsonb,
    actor_user_id uuid,
    actor_kind varchar(16) NOT NULL,
    subject_type varchar(64),
    subject_id varchar(128),
    service_id varchar(128),
    object_seq bigint,
    payload jsonb NOT NULL,
    provenance jsonb NOT NULL,
    correlation_id varchar(64),
    visibility_class varchar(16) NOT NULL,
    CONSTRAINT pk_events PRIMARY KEY (event_id, retention_class, occurred_at),
    CONSTRAINT ck_events_retention_class CHECK (retention_class IN ('business', 'technical')),
    CONSTRAINT ck_events_actor_kind CHECK (actor_kind IN ('user', 'system', 'ai', 'automation', 'plugin'))
) PARTITION BY LIST (retention_class)
"""

SUBPARTITIONS = """
DO $$
DECLARE
    klass text;
    month date;
BEGIN
    FOREACH klass IN ARRAY ARRAY['business', 'technical'] LOOP
        EXECUTE format(
            'CREATE TABLE events.%I PARTITION OF events.events FOR VALUES IN (%L) PARTITION BY RANGE (occurred_at)',
            'events_' || klass, klass
        );
        EXECUTE format('CREATE TABLE events.%I PARTITION OF events.%I DEFAULT',
                       'events_' || klass || '_pdefault', 'events_' || klass);
        month := date_trunc('month', now())::date;
        WHILE month <= (date_trunc('month', now()) + interval '2 months')::date LOOP
            EXECUTE format(
                'CREATE TABLE events.%I PARTITION OF events.%I FOR VALUES FROM (%L) TO (%L)',
                'events_' || klass || '_p' || to_char(month, 'YYYYMM'), 'events_' || klass,
                month, (month + interval '1 month')::date
            );
            month := (month + interval '1 month')::date;
        END LOOP;
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "events"')
    op.execute(CREATE_EVENTS)
    op.execute(SUBPARTITIONS)
    op.create_index("ix_events_seq", "events", ["seq"], schema="events")
    op.create_index("ix_events_type_occurred_at", "events", ["type", "occurred_at"], schema="events")
    op.create_index(
        "ix_events_subject", "events", ["subject_type", "subject_id", "occurred_at"], schema="events"
    )
    op.create_index("ix_events_actor_user_id", "events", ["actor_user_id", "occurred_at"], schema="events")
    for statement in append_only_ddl("events", "events"):
        op.execute(statement)

    op.create_table(
        "dedup_keys",
        sa.Column("type", sa.String(128), nullable=False),
        sa.Column("dedup_key", sa.String(512), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("first_seen_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("type", "dedup_key", name="pk_dedup_keys"),
        schema="events",
    )
    op.create_index("ix_dedup_keys_first_seen_at", "dedup_keys", ["first_seen_at"], schema="events")
    op.create_table(
        "quarantine",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("received_at", TZ, nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("raw", postgresql.JSONB(), nullable=False),
        sa.Column("source_system", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("resolved_by", sa.Uuid()),
        sa.Column("resolved_at", TZ),
        sa.PrimaryKeyConstraint("id", name="pk_quarantine"),
        sa.CheckConstraint(
            "reason IN ('unknown_type', 'invalid_payload', 'version_unsupported', 'pii_detected')",
            name="ck_quarantine_reason",
        ),
        sa.CheckConstraint("status IN ('open', 'released', 'discarded')", name="ck_quarantine_status"),
        schema="events",
    )
    op.create_index("ix_quarantine_status", "quarantine", ["status", "received_at"], schema="events")
    op.create_table(
        "consumer_offsets",
        sa.Column("consumer", sa.String(128), nullable=False),
        sa.Column("last_seq", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("consumer", name="pk_consumer_offsets"),
        schema="events",
    )
    op.create_table(
        "deliveries",
        sa.Column("consumer", sa.String(128), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_seq", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(512)),
        sa.Column("next_attempt_at", TZ),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("consumer", "event_id", name="pk_deliveries"),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'dead')", name="ck_deliveries_status"
        ),
        schema="events",
    )
    op.create_index("ix_deliveries_status", "deliveries", ["status", "updated_at"], schema="events")
    op.create_table(
        "effect_keys",
        sa.Column("consumer", sa.String(128), nullable=False),
        sa.Column("effect_key", sa.String(256), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("consumer", "effect_key", name="pk_effect_keys"),
        schema="events",
    )
    op.create_table(
        "replay_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("projection", sa.String(128), nullable=False),
        sa.Column("from_occurred_at", TZ),
        sa.Column("to_occurred_at", TZ),
        sa.Column("requested_by", sa.Uuid()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("finished_at", TZ),
        sa.PrimaryKeyConstraint("id", name="pk_replay_runs"),
        sa.CheckConstraint("status IN ('running', 'finished', 'failed')", name="ck_replay_runs_status"),
        schema="events",
    )
    # audit ↔ event correlation (T026): same correlation, separate stores (CD-013)
    op.add_column("audit_entries", sa.Column("event_id", sa.Uuid()), schema="audit")


def downgrade() -> None:
    op.drop_column("audit_entries", "event_id", schema="audit")
    for statement in drop_append_only_ddl("events", "events"):
        op.execute(statement)
    for table in ("replay_runs", "effect_keys", "deliveries", "consumer_offsets", "quarantine", "dedup_keys"):
        op.drop_table(table, schema="events")
    op.execute("DROP TABLE events.events CASCADE")
    op.execute('DROP SCHEMA IF EXISTS "events"')
