"""core.live_event — outbox of live notifications for the SSE stream

Revision ID: core_0004
Revises: core_0003
Create Date: 2026-10-01 00:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0004"
down_revision: str | Sequence[str] | None = "core_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_event",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("topic", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("permission", sa.String(128)),
        sa.Column("resource_kind", sa.String(64)),
        sa.Column("resource_id", sa.String(128)),
        sa.Column("audience_user_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("seq", name="pk_live_event"),
        schema="core",
    )
    op.create_index("ix_live_event_created_at", "live_event", ["created_at"], schema="core")


def downgrade() -> None:
    op.drop_table("live_event", schema="core")
