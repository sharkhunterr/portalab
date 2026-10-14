"""notify — an announcement's tag (issue 122): what an automation names its banner by, to take it down
when the thing it announces is over (« parity » …)

Revision ID: notify_0004
Revises: notify_0003
Create Date: 2026-10-15 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "notify_0004"
down_revision: str | Sequence[str] | None = "notify_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("announcements", sa.Column("tag", sa.String(64)), schema="notify")
    op.create_index("ix_announcements_tag", "announcements", ["tag"], schema="notify")


def downgrade() -> None:
    op.drop_index("ix_announcements_tag", "announcements", schema="notify")
    op.drop_column("announcements", "tag", schema="notify")
