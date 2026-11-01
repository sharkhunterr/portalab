"""marketplace schema — when each member last opened the community projects (#303): what was added or
moved on since is new, the badge of « Projects » on the navigation

Revision ID: marketplace_0010
Revises: marketplace_0009
Create Date: 2026-12-04 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "marketplace_0010"
down_revision: str | Sequence[str] | None = "marketplace_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects_seen",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        schema="marketplace",
    )


def downgrade() -> None:
    op.drop_table("projects_seen", schema="marketplace")
