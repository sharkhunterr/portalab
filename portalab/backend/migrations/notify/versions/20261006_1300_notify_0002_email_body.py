"""notify — a communication may bring its own e-mail (a newsletter, 027)

Revision ID: notify_0002
Revises: notify_0001
Create Date: 2026-10-06 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "notify_0002"
down_revision: str | Sequence[str] | None = "notify_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "communications", sa.Column("email_body", postgresql.JSONB(), nullable=True), schema="notify"
    )


def downgrade() -> None:
    op.drop_column("communications", "email_body", schema="notify")
