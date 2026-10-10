"""gamification schema — perks bought in the shop: streak freezes and gains boosts (#54, #55)

A missed day of a play streak covered by a freeze is a ``streak_days`` row marked ``frozen``; the freezes
bought are ``freeze_grants`` (one row per purchase); boosts are ``boosts`` (a factor on some gains for a
time, one row per purchase).

Revision ID: gamification_0006
Revises: gamification_0005
Create Date: 2026-10-10 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "gamification_0006"
down_revision: str | Sequence[str] | None = "gamification_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "streak_days",
        sa.Column("frozen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="gamification",
    )
    op.create_table(
        "freeze_grants",
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("source", name="pk_freeze_grants"),
        schema="gamification",
    )
    op.create_index("ix_freeze_grants_user_id", "freeze_grants", ["user_id"], schema="gamification")
    op.create_table(
        "boosts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("factor", sa.Float(), nullable=False),
        sa.Column("gains", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_boosts"),
        sa.UniqueConstraint("source", name="uq_boosts_source"),
        schema="gamification",
    )
    op.create_index("ix_boosts_user_id", "boosts", ["user_id"], schema="gamification")


def downgrade() -> None:
    op.drop_index("ix_boosts_user_id", table_name="boosts", schema="gamification")
    op.drop_table("boosts", schema="gamification")
    op.drop_index("ix_freeze_grants_user_id", table_name="freeze_grants", schema="gamification")
    op.drop_table("freeze_grants", schema="gamification")
    op.drop_column("streak_days", "frozen", schema="gamification")
