"""marketplace schema — a product's season (#81: highlighted, its season's booster and pack draw from it)
and ``locked``: an item won in a booster before the member meets its level or Contribution (held, not
usable until then)

Revision ID: marketplace_0008
Revises: marketplace_0007
Create Date: 2026-12-02 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "marketplace_0008"
down_revision: str | Sequence[str] | None = "marketplace_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATES = "'active', 'needs_configuration', 'activation_failed', 'revoked', 'refunded', 'expired'"


def upgrade() -> None:
    op.add_column("products", sa.Column("season", sa.String(length=24), nullable=True), schema="marketplace")
    op.create_index("ix_products_season", "products", ["season"], schema="marketplace")
    op.drop_constraint("ck_ownerships_state", "ownerships", schema="marketplace", type_="check")
    op.create_check_constraint(
        "ck_ownerships_state", "ownerships", f"state IN ({STATES}, 'locked')", schema="marketplace"
    )


def downgrade() -> None:
    op.execute("UPDATE marketplace.ownerships SET state = 'revoked' WHERE state = 'locked'")
    op.drop_constraint("ck_ownerships_state", "ownerships", schema="marketplace", type_="check")
    op.create_check_constraint(
        "ck_ownerships_state", "ownerships", f"state IN ({STATES})", schema="marketplace"
    )
    op.drop_index("ix_products_season", table_name="products", schema="marketplace")
    op.drop_column("products", "season", schema="marketplace")
