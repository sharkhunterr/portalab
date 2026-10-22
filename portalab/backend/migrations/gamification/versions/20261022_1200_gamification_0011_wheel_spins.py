"""gamification — the daily wheel's spins: ``wheel_spins`` (issue 225)

One spin per member and day of the economy's time zone: the segment drawn and what it gave.

Revision ID: gamification_0011
Revises: gamification_0010
Create Date: 2026-10-22 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "gamification_0011"
down_revision: str | Sequence[str] | None = "gamification_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wheel_spins",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("segment", sa.String(48), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("product", sa.String(96), nullable=True),
        sa.Column("given", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("spun_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_wheel_spins"),
        sa.UniqueConstraint("user_id", "day", name="uq_wheel_spins_user_day"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_wheel_spins_user", ondelete="CASCADE"
        ),
        schema="gamification",
    )


def downgrade() -> None:
    op.drop_table("wheel_spins", schema="gamification")
