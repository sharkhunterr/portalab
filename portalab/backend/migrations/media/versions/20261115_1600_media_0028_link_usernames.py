"""media — the linked accounts' names on their services, shown in place of their ids.

Revision ID: media_0028
Revises: media_0027
Create Date: 2026-11-15 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0028"
down_revision: str | Sequence[str] | None = "media_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_links", sa.Column("username", sa.String(200), nullable=True), schema="media")


def downgrade() -> None:
    op.drop_column("user_links", "username", schema="media")
