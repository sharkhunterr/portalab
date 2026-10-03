"""content schema — uploaded assets (spec 011 T009)

Revision ID: content_0001
Revises:
Create Date: 2026-10-10 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "content_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("content",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
TABLES = ("assets",)


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "content"')
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_ref", sa.String(length=260), nullable=False),
        sa.Column("blob_key", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=120), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_assets"),
        _user_fk("assets", "uploaded_by", "SET NULL"),
        schema="content",
    )
    op.create_index("ix_assets_owner", "assets", ["owner_ref"], unique=False, schema="content")


def downgrade() -> None:
    for table in TABLES:
        op.drop_table(table, schema="content")
    op.execute('DROP SCHEMA IF EXISTS "content"')
