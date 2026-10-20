"""ai feedback, issue 176 — the member's verdict on an answer (as expected or not, and why)

Revision ID: ai_0002
Revises: ai_0001
Create Date: 2026-12-21 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ai_0002"
down_revision: str | Sequence[str] | None = "ai_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column(
            "message_id",
            sa.Uuid(),
            sa.ForeignKey("ai.messages.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating IN (-1, 1)", name="ck_feedback_rating"),
        schema="ai",
    )
    op.create_index("ix_feedback_rating", "feedback", ["rating", "updated_at"], schema="ai")
    op.create_foreign_key(
        "fk_feedback_user_id_users",
        "feedback",
        "users",
        ["user_id"],
        ["id"],
        source_schema="ai",
        referent_schema="identity",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_rating", table_name="feedback", schema="ai")
    op.drop_table("feedback", schema="ai")
