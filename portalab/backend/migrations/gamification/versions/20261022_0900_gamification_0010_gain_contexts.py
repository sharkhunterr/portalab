"""gamification — what a gain was about (a title, another member): ``gain_contexts``

For a title someone asked for, watched by another member (``media.request_watched``): the title, and who
watched — shown in the administration's journal only.

Revision ID: gamification_0010
Revises: gamification_0009
Create Date: 2026-10-22 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "gamification_0010"
down_revision: str | Sequence[str] | None = "gamification_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gain_contexts",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("object", sa.String(64), nullable=True),
        sa.Column("other_user", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name="pk_gain_contexts"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_gain_contexts_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["other_user"], ["identity.users.id"], name="fk_gain_contexts_other_user", ondelete="SET NULL"
        ),
        schema="gamification",
    )


def downgrade() -> None:
    op.drop_table("gain_contexts", schema="gamification")
