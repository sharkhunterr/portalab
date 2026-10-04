"""media schema — live progress of background tasks (027)

Revision ID: media_0003
Revises: media_0002
Create Date: 2026-10-21 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0003"
down_revision: str | Sequence[str] | None = "media_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "task_progress",
        sa.Column("task", sa.String(length=80), nullable=False),
        sa.Column("running_since", TZ, nullable=True),
        sa.Column("done", sa.BigInteger(), nullable=False),
        sa.Column("total", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("task", name="pk_task_progress"),
        schema="media",
    )


def downgrade() -> None:
    op.drop_table("task_progress", schema="media")
