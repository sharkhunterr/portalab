"""gamification schema — leaderboard snapshots (slice B); moves the ledger's user FK onto ``transactions``

Revision ID: gamification_0002
Revises: gamification_0001
Create Date: 2026-10-17 09:00:00

The initial revision attached the ``transactions`` → ``identity.users`` constraint (RESTRICT) to
``usage_windows`` by mistake; this revision puts it on the ledger, where it belongs.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "gamification_0002"
down_revision: str | Sequence[str] | None = "gamification_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)
MISPLACED = "fk_transactions_user_id_users"


def upgrade() -> None:
    op.create_table(
        "leaderboard_snapshots",
        sa.Column("metric", sa.String(length=32), nullable=False),
        sa.Column("period", sa.String(length=8), nullable=False),
        sa.Column("period_start", TZ, nullable=True),
        sa.Column("computed_at", TZ, nullable=False),
        sa.Column("entries", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("period IN ('all', 'month', 'week')", name="ck_leaderboard_snapshots_period"),
        sa.PrimaryKeyConstraint("metric", "period", name="pk_leaderboard_snapshots"),
        schema="gamification",
    )
    op.drop_constraint(MISPLACED, "usage_windows", schema="gamification", type_="foreignkey")
    op.create_foreign_key(
        MISPLACED,
        "transactions",
        "users",
        ["user_id"],
        ["id"],
        source_schema="gamification",
        referent_schema="identity",
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(MISPLACED, "transactions", schema="gamification", type_="foreignkey")
    op.create_foreign_key(
        MISPLACED,
        "usage_windows",
        "users",
        ["user_id"],
        ["id"],
        source_schema="gamification",
        referent_schema="identity",
        ondelete="RESTRICT",
    )
    op.drop_table("leaderboard_snapshots", schema="gamification")
