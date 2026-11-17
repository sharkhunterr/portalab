"""core.job — the failed and dead jobs indexed, the table vacuumed sooner (issue 494)

The jobs' health check counts the failed and dead jobs: without an index it read the whole table (1.8 M
rows on a busy portal) at every check. The table churns tens of thousands of rows a day: autovacuum runs
sooner, so the partial indexes on queued and running jobs stay small.

Revision ID: core_0006
Revises: core_0005
Create Date: 2026-11-17 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "core_0006"
down_revision: str | Sequence[str] | None = "core_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_job_failures",
        "job",
        ["status"],
        schema="core",
        postgresql_where=sa.text("status IN ('failed', 'dead')"),
    )
    op.execute(
        "ALTER TABLE core.job SET (autovacuum_vacuum_scale_factor = 0.02, autovacuum_analyze_scale_factor = 0.02)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE core.job RESET (autovacuum_vacuum_scale_factor, autovacuum_analyze_scale_factor)")
    op.drop_index("ix_job_failures", table_name="job", schema="core")
