"""notify — the parameters of the repeats merged into one notification (#258)

A series of rewards (the radio's quarters of an hour) merges into one item: it shows what they brought in all,
not only the first's. ``params`` keeps the merged parameters; empty, the item's communication's are shown.

Revision ID: notify_0006
Revises: notify_0005
Create Date: 2026-10-27 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "notify_0006"
down_revision: str | Sequence[str] | None = "notify_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("params", postgresql.JSONB(), nullable=True), schema="notify")


def downgrade() -> None:
    op.drop_column("notifications", "params", schema="notify")
