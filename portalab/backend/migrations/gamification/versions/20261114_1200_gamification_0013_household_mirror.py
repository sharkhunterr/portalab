"""gamification — a ledger row mirrored on a household's master names the profile it came from (spec 032)

Revision ID: gamification_0013
Revises: gamification_0012
Create Date: 2026-11-14 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "gamification_0013"
down_revision: str | Sequence[str] | None = "gamification_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("profile_id", sa.Uuid(), nullable=True), schema="gamification")


def downgrade() -> None:
    op.drop_column("transactions", "profile_id", schema="gamification")
