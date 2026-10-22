"""support — a feedback's history: each reply in its own words, read, closed, reopened, converted, rewarded

Revision ID: support_0005
Revises: support_0004
Create Date: 2026-10-22 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "support_0005"
down_revision: str | Sequence[str] | None = "support_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedback_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "feedback_id",
            sa.Uuid(),
            sa.ForeignKey("support.feedback_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("detail", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("identity.users.id", ondelete="SET NULL")),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('replied', 'read', 'closed', 'reopened', 'converted', 'rewarded')",
            name="ck_feedback_events_kind",
        ),
        schema="support",
    )
    op.create_index("ix_feedback_events_feedback", "feedback_events", ["feedback_id", "at"], schema="support")


def downgrade() -> None:
    op.drop_index("ix_feedback_events_feedback", table_name="feedback_events", schema="support")
    op.drop_table("feedback_events", schema="support")
