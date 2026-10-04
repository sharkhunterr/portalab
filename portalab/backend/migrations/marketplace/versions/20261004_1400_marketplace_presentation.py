"""marketplace shop presentation — rarity, featured, poster effect, icon; collection icons (spec 027 T088)

Merchandising attributes only: they never take part in a product version (price, conditions and history are
untouched). Existing products become ``common``, not featured, with the ``auto`` poster effect.

Revision ID: marketplace_0003
Revises: marketplace_0002
Create Date: 2026-10-04 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "marketplace_0003"
down_revision: str | Sequence[str] | None = "marketplace_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("rarity", sa.String(12), nullable=False, server_default="common"),
        schema="marketplace",
    )
    op.add_column(
        "products",
        sa.Column("featured", sa.Boolean(), nullable=False, server_default="false"),
        schema="marketplace",
    )
    op.add_column(
        "products",
        sa.Column("poster_effect", sa.String(12), nullable=False, server_default="auto"),
        schema="marketplace",
    )
    op.add_column("products", sa.Column("icon", sa.String(64), nullable=True), schema="marketplace")
    op.add_column("categories", sa.Column("icon", sa.String(64), nullable=True), schema="marketplace")
    op.create_check_constraint(
        "ck_products_rarity",
        "products",
        "rarity IN ('common', 'rare', 'epic', 'legendary')",
        schema="marketplace",
    )
    op.create_check_constraint(
        "ck_products_poster_effect",
        "products",
        "poster_effect IN ('auto', 'none', 'shine', 'glitch', 'spin', 'neon', 'blink')",
        schema="marketplace",
    )


def downgrade() -> None:
    op.drop_constraint("ck_products_poster_effect", "products", schema="marketplace")
    op.drop_constraint("ck_products_rarity", "products", schema="marketplace")
    op.drop_column("categories", "icon", schema="marketplace")
    for column in ("icon", "poster_effect", "featured", "rarity"):
        op.drop_column("products", column, schema="marketplace")
