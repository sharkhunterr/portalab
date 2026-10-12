"""marketplace schema — boosters (#81): the boosters members opened, the reserve of items they keep, and
``booster`` as an ownership's origin

Revision ID: marketplace_0007
Revises: marketplace_0006
Create Date: 2026-12-01 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "marketplace_0007"
down_revision: str | Sequence[str] | None = "marketplace_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_ownerships_origin", "ownerships", schema="marketplace", type_="check")
    op.create_check_constraint(
        "ck_ownerships_origin",
        "ownerships",
        "origin IN ('purchase', 'grant', 'booster')",
        schema="marketplace",
    )
    op.create_table(
        "booster_openings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("booster_key", sa.String(length=64), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False),
        sa.Column("refund", sa.BigInteger(), nullable=False),
        sa.Column("spend_tx_ref", sa.Uuid(), nullable=True),
        sa.Column("refund_tx_ref", sa.Uuid(), nullable=True),
        sa.Column("drawn", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price >= 0 AND refund >= 0", name=op.f("ck_booster_openings_amounts")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_booster_openings_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booster_openings")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_booster_openings_idempotency_key")),
        schema="marketplace",
    )
    op.create_index(
        "ix_booster_openings_user", "booster_openings", ["user_id", "opened_at"], schema="marketplace"
    )
    op.create_index(
        "ix_booster_openings_user_booster",
        "booster_openings",
        ["user_id", "booster_key"],
        schema="marketplace",
    )
    op.create_table(
        "reserve",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity >= 0", name=op.f("ck_reserve_quantity")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_reserve_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["marketplace.products.id"], name=op.f("fk_reserve_product_id_products")
        ),
        sa.PrimaryKeyConstraint("user_id", "product_id", name=op.f("pk_reserve")),
        schema="marketplace",
    )


def downgrade() -> None:
    op.drop_table("reserve", schema="marketplace")
    op.drop_index("ix_booster_openings_user_booster", table_name="booster_openings", schema="marketplace")
    op.drop_index("ix_booster_openings_user", table_name="booster_openings", schema="marketplace")
    op.drop_table("booster_openings", schema="marketplace")
    op.execute("DELETE FROM marketplace.ownerships WHERE origin = 'booster'")
    op.drop_constraint("ck_ownerships_origin", "ownerships", schema="marketplace", type_="check")
    op.create_check_constraint(
        "ck_ownerships_origin", "ownerships", "origin IN ('purchase', 'grant')", schema="marketplace"
    )
