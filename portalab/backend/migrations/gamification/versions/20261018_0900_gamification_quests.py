"""gamification schema — quests, daily objectives and challenges (slice C)

Revision ID: gamification_0003
Revises: gamification_0002
Create Date: 2026-10-18 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "gamification_0003"
down_revision: str | Sequence[str] | None = "gamification_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "quests",
        sa.Column("key", sa.String(length=96), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("effective_from", TZ, nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("kind IN ('quest', 'daily', 'challenge')", name="ck_quests_kind"),
        sa.CheckConstraint("status IN ('active', 'retired')", name="ck_quests_status"),
        sa.PrimaryKeyConstraint("key", "version", name="pk_quests"),
        schema="gamification",
    )
    op.create_table(
        "quest_progress",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("quest_key", sa.String(length=160), nullable=False),
        sa.Column("period_key", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False),
        sa.Column("completed_at", TZ, nullable=True),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("user_id", "quest_key", "period_key", name="pk_quest_progress"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_quest_progress_user_id_users", ondelete="CASCADE"
        ),
        schema="gamification",
    )


def downgrade() -> None:
    op.drop_table("quest_progress", schema="gamification")
    op.drop_table("quests", schema="gamification")
