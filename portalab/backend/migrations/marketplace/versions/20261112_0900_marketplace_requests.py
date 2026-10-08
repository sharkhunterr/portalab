"""marketplace schema — requests to handle: a special request (a film in 4K with the member's wishes) or
access to a service, opened by a purchase and handled by the administrators by a deadline (027)

Revision ID: marketplace_0006
Revises: marketplace_0005
Create Date: 2026-11-12 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "marketplace_0006"
down_revision: str | Sequence[str] | None = "marketplace_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ownership_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('special', 'service')", name=op.f("ck_requests_kind")),
        sa.CheckConstraint(
            "state IN ('pending', 'in_progress', 'done', 'declined')", name=op.f("ck_requests_state")
        ),
        sa.ForeignKeyConstraint(
            ["ownership_id"], ["marketplace.ownerships.id"], name=op.f("fk_requests_ownership_id_ownerships")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["marketplace.products.id"], name=op.f("fk_requests_product_id_products")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requests")),
        sa.UniqueConstraint("ownership_id", name=op.f("uq_requests_ownership_id")),
        schema="marketplace",
    )
    op.create_index("ix_requests_state_due", "requests", ["state", "due_at"], schema="marketplace")
    op.create_index("ix_requests_user", "requests", ["user_id", "created_at"], schema="marketplace")


def downgrade() -> None:
    op.drop_index("ix_requests_user", table_name="requests", schema="marketplace")
    op.drop_index("ix_requests_state_due", table_name="requests", schema="marketplace")
    op.drop_table("requests", schema="marketplace")
