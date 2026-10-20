"""ai perks, issue 173 — the assistant's capacities a member bought in the shop

Revision ID: ai_0003
Revises: ai_0002
Create Date: 2026-12-22 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ai_0003"
down_revision: str | Sequence[str] | None = "ai_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "perks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("perk", sa.String(32), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remaining", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_ref", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("source_ref", name="uq_perks_source_ref"),
        schema="ai",
    )
    op.create_index("ix_perks_user_id", "perks", ["user_id", "perk"], schema="ai")
    op.create_foreign_key(
        "fk_perks_user_id_users",
        "perks",
        "users",
        ["user_id"],
        ["id"],
        source_schema="ai",
        referent_schema="identity",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_index("ix_perks_user_id", table_name="perks", schema="ai")
    op.drop_table("perks", schema="ai")
