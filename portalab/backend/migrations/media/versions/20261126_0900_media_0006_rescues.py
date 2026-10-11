"""media — rescues: saving a title from the cleanup tool's deletion (#57)

``media.rescues``: a member's ledger — credited by the shop, spent saving a title (Maintainerr's
exclusion); the balance is the sum of ``delta``.

Revision ID: media_0006
Revises: media_0005
Create Date: 2026-11-26 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0006"
down_revision: str | Sequence[str] | None = "media_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "rescues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=12), nullable=False),
        sa.Column("source_ref", sa.String(length=200), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint("reason IN ('purchase', 'rescue', 'admin')", name="ck_rescues_reason"),
        sa.PrimaryKeyConstraint("id", name="pk_rescues"),
        sa.UniqueConstraint("source_ref", name="uq_rescues_source_ref"),
        schema="media",
    )
    op.create_index("ix_rescues_user", "rescues", ["user_id"], schema="media")
    op.create_index("ix_rescues_object", "rescues", ["object_id"], schema="media")


def downgrade() -> None:
    op.drop_index("ix_rescues_object", table_name="rescues", schema="media")
    op.drop_index("ix_rescues_user", table_name="rescues", schema="media")
    op.drop_table("rescues", schema="media")
