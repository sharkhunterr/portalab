"""marketplace schema — what came into a member's reserve since they last opened it (#81): when each item
was last received, and when each member last looked — the reserve's badge on the navigation

Revision ID: marketplace_0009
Revises: marketplace_0008
Create Date: 2026-12-03 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "marketplace_0009"
down_revision: str | Sequence[str] | None = "marketplace_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reserve", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True), schema="marketplace"
    )
    # what is there already was received when last changed (every member's badge starts from their visit)
    op.execute("UPDATE marketplace.reserve SET received_at = updated_at")
    op.create_table(
        "reserve_seen",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        schema="marketplace",
    )


def downgrade() -> None:
    op.drop_table("reserve_seen", schema="marketplace")
    op.drop_column("reserve", "received_at", schema="marketplace")
