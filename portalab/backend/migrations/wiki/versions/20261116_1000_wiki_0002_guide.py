"""wiki — Portalab's own member guide: which pages of the guide this wiki holds (issue 457)

Revision ID: wiki_0002
Revises: wiki_0001
Create Date: 2026-11-16 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "wiki_0002"
down_revision: str | Sequence[str] | None = "wiki_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guide_pages",
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("state IN ('installed', 'removed', 'dismissed')", name="ck_guide_pages_state"),
        sa.ForeignKeyConstraint(
            ["page_id"], ["wiki.pages.id"], name="fk_guide_pages_page_id_pages", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("slug", name="pk_guide_pages"),
        schema="wiki",
    )


def downgrade() -> None:
    op.drop_table("guide_pages", schema="wiki")
