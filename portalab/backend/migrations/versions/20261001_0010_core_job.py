"""core.job — durable jobs / transactional outbox

Revision ID: core_0002
Revises: core_0001
Create Date: 2026-10-01 00:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0002"
down_revision: str | Sequence[str] | None = "core_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("queue", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("dedup_key", sa.String(512)),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("locked_by", sa.String(128)),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_job"),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','dead')", name="ck_job_status_valid"
        ),
        sa.CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="ck_job_attempts_valid"),
        schema="core",
    )
    op.create_index(
        "ix_job_claimable",
        "job",
        ["queue", "run_at"],
        schema="core",
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "ix_job_running_locks",
        "job",
        ["queue", "locked_until"],
        schema="core",
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_index(
        "uq_job_queue_dedup_key",
        "job",
        ["queue", "dedup_key"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("dedup_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("job", schema="core")
