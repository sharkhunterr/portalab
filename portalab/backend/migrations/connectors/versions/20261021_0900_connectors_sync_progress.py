"""connectors schema — live progress of the running sync (027)

Revision ID: connectors_0002
Revises: connectors_0001
Create Date: 2026-10-21 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "connectors_0002"
down_revision: str | Sequence[str] | None = "connectors_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sync_state", sa.Column("progress", postgresql.JSONB(), nullable=True), schema="connectors")


def downgrade() -> None:
    op.drop_column("sync_state", "progress", schema="connectors")
