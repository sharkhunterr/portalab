"""support — an incident may also be shown as a banner across the portal while it is open (like a
maintenance announced as a banner)

Revision ID: support_0004
Revises: support_0003
Create Date: 2026-10-21 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "support_0004"
down_revision: str | Sequence[str] | None = "support_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("banner", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="support",
    )


def downgrade() -> None:
    op.drop_column("incidents", "banner", schema="support")
