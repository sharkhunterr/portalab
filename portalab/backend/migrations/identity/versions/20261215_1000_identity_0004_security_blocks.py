"""identity schema — the intrusion guard's blocks, kept across restarts (spec 028 T058)

Revision ID: identity_0004
Revises: identity_0003
Create Date: 2026-12-15 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "identity_0004"
down_revision: str | Sequence[str] | None = "identity_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "security_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(128), nullable=False),
        sa.Column("label", sa.String(128), nullable=True),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("paths", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("until", TZ, nullable=False),
        sa.Column("lifted_at", TZ, nullable=True),
        sa.Column("lifted_by", sa.String(128), nullable=True),
        sa.CheckConstraint("kind IN ('account', 'session', 'address')", name=op.f("ck_security_blocks_kind")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_blocks")),
        schema="identity",
    )
    op.create_index(
        "ix_security_blocks_active",
        "security_blocks",
        ["kind", "subject"],
        schema="identity",
        postgresql_where=sa.text("lifted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_security_blocks_active", table_name="security_blocks", schema="identity")
    op.drop_table("security_blocks", schema="identity")
