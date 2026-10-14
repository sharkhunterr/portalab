"""automations — service signal values (issue 122): the last value seen of each watched signal per
service, to publish ``service.signal_changed`` only when it changes

Revision ID: automations_0002
Revises: automations_0001
Create Date: 2026-10-15 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "automations_0002"
down_revision: str | Sequence[str] | None = "automations_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signal_values",
        sa.Column("service_id", sa.String(128), primary_key=True),
        sa.Column("signal", sa.String(128), primary_key=True),
        sa.Column("value", postgresql.JSONB()),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        schema="automations",
    )


def downgrade() -> None:
    op.drop_table("signal_values", schema="automations")
