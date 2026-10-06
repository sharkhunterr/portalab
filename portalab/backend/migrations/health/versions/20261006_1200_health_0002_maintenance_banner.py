"""health — a maintenance may also be announced as a banner across the portal (027)

Revision ID: health_0002
Revises: health_0001
Create Date: 2026-10-06 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "health_0002"
down_revision: str | Sequence[str] | None = "health_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "maintenance_windows",
        sa.Column("banner", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="health",
    )


def downgrade() -> None:
    op.drop_column("maintenance_windows", "banner", schema="health")
