"""notify — whether each member may close an announcement's banner (chosen by the administrator; the
urgent ones sent so far could not be closed, so they keep it that way)

Revision ID: notify_0005
Revises: notify_0004
Create Date: 2026-10-21 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "notify_0005"
down_revision: str | Sequence[str] | None = "notify_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "announcements",
        sa.Column("dismissible", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="notify",
    )
    op.execute("UPDATE notify.announcements SET dismissible = false WHERE tone = 'critical'")


def downgrade() -> None:
    op.drop_column("announcements", "dismissible", schema="notify")
