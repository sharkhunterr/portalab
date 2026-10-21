"""media — requests to the radio's DJ: free ones each day, then credits bought in the shop (issue 184)

Revision ID: media_0012
Revises: media_0011
Create Date: 2026-12-22 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0012"
down_revision: str | Sequence[str] | None = "media_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "radio_credits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=12), nullable=False),
        sa.Column("source_ref", sa.String(length=200), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint("reason IN ('purchase', 'ask', 'admin')", name="ck_radio_credits_reason"),
        sa.PrimaryKeyConstraint("id", name="pk_radio_credits"),
        sa.UniqueConstraint("source_ref", name="uq_radio_credits_source_ref"),
        schema="media",
    )
    op.create_index("ix_radio_credits_user", "radio_credits", ["user_id", "created_at"], schema="media")


def downgrade() -> None:
    op.drop_index("ix_radio_credits_user", table_name="radio_credits", schema="media")
    op.drop_table("radio_credits", schema="media")
