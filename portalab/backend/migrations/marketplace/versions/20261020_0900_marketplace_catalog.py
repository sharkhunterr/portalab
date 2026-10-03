"""marketplace schema — catalog: categories, products, versions, ownerships, refunds (slice B)

Revision ID: marketplace_0002
Revises: marketplace_0001
Create Date: 2026-10-20 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "marketplace_0002"
down_revision: str | Sequence[str] | None = "marketplace_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)
TABLES = ("refunds", "product_versions", "ownerships", "products", "categories")
APPEND_ONLY = ("product_versions", "refunds")


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("label_key", sa.String(length=160), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint("key", name="uq_categories_key"),
        schema="marketplace",
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=96), nullable=False),
        sa.Column("type", sa.String(length=96), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("repeatable", sa.Boolean(), nullable=False),
        sa.Column("extension_ref", sa.String(length=120), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint(
            "state IN ('draft', 'available', 'unavailable', 'archived')", name="ck_products_state"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["marketplace.categories.id"], name="fk_products_category_id_categories"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("key", name="uq_products_key"),
        _user_fk("products", "created_by", "SET NULL"),
        schema="marketplace",
    )
    op.create_index(
        "ix_products_state", "products", ["state", "category_id"], unique=False, schema="marketplace"
    )
    op.create_table(
        "ownerships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("origin", sa.String(length=10), nullable=False),
        sa.Column("repeatable", sa.Boolean(), nullable=False),
        sa.Column("product_version", sa.Integer(), nullable=False),
        sa.Column("price_paid", sa.BigInteger(), nullable=False),
        sa.Column("conditions_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("purchase_tx_ref", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column("activation_detail", sa.String(length=200), nullable=True),
        sa.Column("activation_attempts", sa.Integer(), nullable=False),
        sa.Column("acquired_at", TZ, nullable=False),
        sa.Column("expires_at", TZ, nullable=True),
        sa.Column("revoked_at", TZ, nullable=True),
        sa.Column("revoke_ground", sa.String(length=24), nullable=True),
        sa.Column("revoke_reason", sa.String(length=500), nullable=True),
        sa.CheckConstraint("origin IN ('purchase', 'grant')", name="ck_ownerships_origin"),
        sa.CheckConstraint(
            "state IN ('active', 'needs_configuration', 'activation_failed', 'revoked', 'refunded', 'expired')",
            name="ck_ownerships_state",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["marketplace.products.id"], name="fk_ownerships_product_id_products"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ownerships"),
        sa.UniqueConstraint("idempotency_key", name="uq_ownerships_idempotency_key"),
        _user_fk("ownerships", "user_id", "RESTRICT"),
        schema="marketplace",
    )
    op.create_index(
        "ix_ownerships_user", "ownerships", ["user_id", "acquired_at"], unique=False, schema="marketplace"
    )
    op.create_index(
        "uq_ownerships_permanent",
        "ownerships",
        ["user_id", "product_id"],
        unique=True,
        schema="marketplace",
        postgresql_where=sa.text("state NOT IN ('revoked', 'refunded', 'expired') AND NOT repeatable"),
    )
    op.create_table(
        "product_versions",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("price_coins", sa.BigInteger(), nullable=True),
        sa.Column("conditions", postgresql.JSONB(), nullable=False),
        sa.Column("refund_policy", postgresql.JSONB(), nullable=False),
        sa.Column("names", postgresql.JSONB(), nullable=False),
        sa.Column("descriptions", postgresql.JSONB(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("config_required", sa.Boolean(), nullable=False),
        sa.Column("effective_from", TZ, nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["product_id"], ["marketplace.products.id"], name="fk_product_versions_product_id_products"
        ),
        sa.PrimaryKeyConstraint("product_id", "version", name="pk_product_versions"),
        _user_fk("product_versions", "changed_by", "RESTRICT"),
        schema="marketplace",
        info={"portalab_append_only": True},
    )
    op.create_table(
        "refunds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ownership_id", sa.Uuid(), nullable=False),
        sa.Column("refund_tx_ref", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("percent", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["ownership_id"], ["marketplace.ownerships.id"], name="fk_refunds_ownership_id_ownerships"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refunds"),
        _user_fk("refunds", "actor_user_id", "RESTRICT"),
        schema="marketplace",
        info={"portalab_append_only": True},
    )
    for table in APPEND_ONLY:
        for statement in append_only_ddl("marketplace", table):
            op.execute(statement)


def downgrade() -> None:
    for table in APPEND_ONLY:
        for statement in drop_append_only_ddl("marketplace", table):
            op.execute(statement)
    for table in TABLES:
        op.drop_table(table, schema="marketplace")
