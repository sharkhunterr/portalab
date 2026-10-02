"""audit initial schema — append-only audit.audit_entries, the AuditSink target (spec 003 T006)

Revision ID: audit_0001
Revises:
Create Date: 2026-10-01 20:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "audit_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("audit",)
depends_on: str | Sequence[str] | None = ("core_0003",)

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "audit"')
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.Column("received_at", TZ, nullable=False),
        sa.Column("actor_user_id", sa.Uuid()),
        sa.Column("actor_kind", sa.String(16), nullable=False),
        sa.Column("acting_for", sa.Uuid()),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64)),
        sa.Column("resource_id", sa.String(128)),
        sa.Column("scope", sa.String(128)),
        sa.Column("decision", sa.String(8), nullable=False),
        sa.Column("result", sa.String(8), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("correlation_id", sa.String(64)),
        sa.PrimaryKeyConstraint("id", name="pk_audit_entries"),
        sa.UniqueConstraint("seq", name="uq_audit_entries_seq"),
        sa.CheckConstraint("decision IN ('allow', 'deny', 'n/a')", name="ck_audit_entries_decision"),
        sa.CheckConstraint("result IN ('success', 'failure', 'n/a')", name="ck_audit_entries_result"),
        sa.CheckConstraint(
            "actor_kind IN ('user', 'system', 'ai', 'automation', 'plugin', 'anonymous')",
            name="ck_audit_entries_actor_kind",
        ),
        schema="audit",
    )
    op.create_index("ix_audit_entries_occurred_at", "audit_entries", ["occurred_at"], schema="audit")
    op.create_index("ix_audit_entries_actor_user_id", "audit_entries", ["actor_user_id"], schema="audit")
    for statement in append_only_ddl("audit", "audit_entries"):
        op.execute(statement)


def downgrade() -> None:
    for statement in drop_append_only_ddl("audit", "audit_entries"):
        op.execute(statement)
    op.drop_table("audit_entries", schema="audit")
    op.execute('DROP SCHEMA IF EXISTS "audit"')
