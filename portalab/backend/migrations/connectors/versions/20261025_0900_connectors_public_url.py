"""connectors schema — a service's public address for members' quick links (027)

Revision ID: connectors_0003
Revises: connectors_0002
Create Date: 2026-10-25 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "connectors_0003"
down_revision: str | Sequence[str] | None = "connectors_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "services", sa.Column("public_url", sa.String(length=512), nullable=True), schema="connectors"
    )


def downgrade() -> None:
    op.drop_column("services", "public_url", schema="connectors")
