"""audit.audit_entries → monthly range partitions + audit.audit_checkpoints (spec 021 T018, R7)

Expand/contract in one step while the volume is low: build the partitioned table, copy every row keeping its
``seq``, swap, drop the old table. Append-only triggers are recreated on the partitioned parent (row triggers
propagate to partitions). Retention removes whole partitions only (R5).

Revision ID: audit_0002
Revises: audit_0001
Create Date: 2026-10-02 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "audit_0002"
down_revision: str | Sequence[str] | None = "audit_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (
    "id, seq, occurred_at, received_at, actor_user_id, actor_kind, acting_for, action, resource_type, "
    "resource_id, scope, decision, result, context, correlation_id"
)

CREATE_PARTITIONED = """
CREATE TABLE audit.audit_entries (
    id uuid NOT NULL,
    seq bigint GENERATED ALWAYS AS IDENTITY,
    occurred_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL,
    actor_user_id uuid,
    actor_kind varchar(16) NOT NULL,
    acting_for uuid,
    action varchar(128) NOT NULL,
    resource_type varchar(64),
    resource_id varchar(128),
    scope varchar(128),
    decision varchar(8) NOT NULL,
    result varchar(8) NOT NULL,
    context jsonb NOT NULL DEFAULT '{}'::jsonb,
    correlation_id varchar(64),
    CONSTRAINT pk_audit_entries PRIMARY KEY (id, occurred_at),
    CONSTRAINT ck_audit_entries_decision CHECK (decision IN ('allow', 'deny', 'n/a')),
    CONSTRAINT ck_audit_entries_result CHECK (result IN ('success', 'failure', 'n/a')),
    CONSTRAINT ck_audit_entries_actor_kind
        CHECK (actor_kind IN ('user', 'system', 'ai', 'automation', 'plugin', 'anonymous'))
) PARTITION BY RANGE (occurred_at)
"""

MONTHLY_PARTITIONS = """
DO $$
DECLARE
    month date := date_trunc('month', LEAST(now(), COALESCE((SELECT min(occurred_at) FROM audit.audit_entries_legacy), now())))::date;
    last date := (date_trunc('month', now()) + interval '2 months')::date;
BEGIN
    WHILE month <= last LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS audit.%I PARTITION OF audit.audit_entries FOR VALUES FROM (%L) TO (%L)',
            'audit_entries_p' || to_char(month, 'YYYYMM'), month, (month + interval '1 month')::date
        );
        month := (month + interval '1 month')::date;
    END LOOP;
END $$;
"""


def upgrade() -> None:
    for statement in drop_append_only_ddl("audit", "audit_entries"):
        op.execute(statement)
    op.execute("ALTER TABLE audit.audit_entries RENAME TO audit_entries_legacy")
    op.execute(
        "ALTER TABLE audit.audit_entries_legacy RENAME CONSTRAINT pk_audit_entries TO pk_audit_entries_legacy"
    )
    op.execute("ALTER TABLE audit.audit_entries_legacy DROP CONSTRAINT uq_audit_entries_seq")
    for name in ("decision", "result", "actor_kind"):
        op.execute(f"ALTER TABLE audit.audit_entries_legacy DROP CONSTRAINT ck_audit_entries_{name}")
    op.execute("DROP INDEX audit.ix_audit_entries_occurred_at")
    op.execute("DROP INDEX audit.ix_audit_entries_actor_user_id")
    op.execute(CREATE_PARTITIONED)
    op.execute(MONTHLY_PARTITIONS)
    op.execute("CREATE TABLE audit.audit_entries_pdefault PARTITION OF audit.audit_entries DEFAULT")
    op.execute(
        f"INSERT INTO audit.audit_entries ({COLUMNS}) OVERRIDING SYSTEM VALUE "  # noqa: S608 — constant columns
        f"SELECT {COLUMNS} FROM audit.audit_entries_legacy"
    )
    op.execute(
        "SELECT setval(pg_get_serial_sequence('audit.audit_entries', 'seq'), "
        "COALESCE((SELECT max(seq) FROM audit.audit_entries), 0) + 1, false)"
    )
    op.execute("DROP TABLE audit.audit_entries_legacy")
    op.create_index("ix_audit_entries_occurred_at", "audit_entries", ["occurred_at"], schema="audit")
    op.create_index("ix_audit_entries_actor_user_id", "audit_entries", ["actor_user_id"], schema="audit")
    op.create_index("ix_audit_entries_seq", "audit_entries", ["seq"], schema="audit")
    for statement in append_only_ddl("audit", "audit_entries"):
        op.execute(statement)

    op.create_table(
        "audit_checkpoints",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("from_seq", sa.BigInteger(), nullable=False),
        sa.Column("to_seq", sa.BigInteger(), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("batch_hash", sa.String(64), nullable=False),
        sa.Column("prev_checkpoint_hash", sa.String(64), nullable=False),
        sa.Column("checkpoint_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_checkpoints"),
        sa.UniqueConstraint("to_seq", name="uq_audit_checkpoints_to_seq"),
        schema="audit",
    )
    for statement in append_only_ddl("audit", "audit_checkpoints"):
        op.execute(statement)


def downgrade() -> None:
    """Development only: back to a plain table (checkpoints dropped)."""
    for statement in drop_append_only_ddl("audit", "audit_checkpoints"):
        op.execute(statement)
    op.drop_table("audit_checkpoints", schema="audit")
    for statement in drop_append_only_ddl("audit", "audit_entries"):
        op.execute(statement)
    op.execute("ALTER TABLE audit.audit_entries RENAME TO audit_entries_partitioned")
    op.execute("CREATE TABLE audit.audit_entries (LIKE audit.audit_entries_partitioned INCLUDING DEFAULTS)")
    op.execute(
        f"INSERT INTO audit.audit_entries ({COLUMNS}) "  # noqa: S608 — constant column list
        f"SELECT {COLUMNS} FROM audit.audit_entries_partitioned"
    )
    op.execute("DROP TABLE audit.audit_entries_partitioned")
