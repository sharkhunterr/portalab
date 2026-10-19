"""observability — the log journal (issue 158)

``obs.log_entries``: the lines of the server's and the worker's logs, already redacted, kept a few days for
the administrators (bounded by age — retention target ``observability.logs`` — and by count).

Revision ID: observability_0002
Revises: observability_0001
Create Date: 2026-12-19 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "observability_0002"
down_revision: str | Sequence[str] | None = "observability_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "log_entries",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("at", TZ, nullable=False),
        sa.Column("process", sa.String(32), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("logger", sa.String(200), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("seq", name="pk_log_entries"),
        schema="obs",
    )
    op.create_index("ix_log_entries_at", "log_entries", ["at"], schema="obs")
    op.create_index("ix_log_entries_correlation", "log_entries", ["correlation_id"], schema="obs")
    op.create_index("ix_log_entries_source_seq", "log_entries", ["source", "seq"], schema="obs")


def downgrade() -> None:
    op.drop_table("log_entries", schema="obs")
