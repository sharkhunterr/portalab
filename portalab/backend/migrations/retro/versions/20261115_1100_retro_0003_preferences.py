"""retro schema — the members' emulator settings per core (issue 421).

Revision ID: retro_0003
Revises: retro_0002
Create Date: 2026-11-15 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "retro_0003"
down_revision: str | Sequence[str] | None = "retro_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("core", sa.String(64), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name=op.f("fk_preferences_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "core", name=op.f("pk_preferences")),
        schema="retro",
    )


def downgrade() -> None:
    op.drop_table("preferences", schema="retro")
