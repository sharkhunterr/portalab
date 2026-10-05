"""marketplace schema — profile cosmetics a member wears (027)

Revision ID: marketplace_0004
Revises: marketplace_0003
Create Date: 2026-10-22 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "marketplace_0004"
down_revision: str | Sequence[str] | None = "marketplace_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "equipped",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("slot", sa.String(length=16), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_equipped_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "slot", name="pk_equipped"),
        schema="marketplace",
    )


def downgrade() -> None:
    op.drop_table("equipped", schema="marketplace")
