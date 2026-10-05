"""marketplace schema — scarcity: supply per rarity, product supply and purchase limits (027)

Revision ID: marketplace_0005
Revises: marketplace_0004
Create Date: 2026-10-23 09:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "marketplace_0005"
down_revision: str | Sequence[str] | None = "marketplace_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# common products are unlimited; the rarer, the fewer copies (administrators change these)
SUPPLY = {"common": None, "rare": 50, "epic": 15, "legendary": 2}


def upgrade() -> None:
    rarities = op.create_table(
        "rarities",
        sa.Column("key", sa.String(length=12), nullable=False),
        sa.Column("supply", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("supply IS NULL OR supply >= 1", name=op.f("ck_rarities_supply")),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_rarities")),
        schema="marketplace",
    )
    now = datetime.now(UTC)
    op.bulk_insert(rarities, [{"key": k, "supply": v, "updated_at": now} for k, v in SUPPLY.items()])
    op.add_column("products", sa.Column("supply", sa.Integer(), nullable=True), schema="marketplace")
    op.add_column("products", sa.Column("limit_count", sa.Integer(), nullable=True), schema="marketplace")
    op.add_column("products", sa.Column("limit_days", sa.Integer(), nullable=True), schema="marketplace")


def downgrade() -> None:
    op.drop_column("products", "limit_days", schema="marketplace")
    op.drop_column("products", "limit_count", schema="marketplace")
    op.drop_column("products", "supply", schema="marketplace")
    op.drop_table("rarities", schema="marketplace")
