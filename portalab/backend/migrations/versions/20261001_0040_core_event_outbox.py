"""core.event_outbox — domain-event envelopes published in the producer's transaction (spec 002 T004)

Revision ID: core_0005
Revises: core_0004
Create Date: 2026-10-01 00:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "core_0005"
down_revision: str | Sequence[str] | None = "core_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_outbox",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("actor_channel", sa.String(16)),
        sa.Column("subject_kind", sa.String(64)),
        sa.Column("subject_id", sa.String(128)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("dedup_key", sa.String(256)),
        sa.PrimaryKeyConstraint("seq", name="pk_event_outbox"),
        sa.UniqueConstraint("event_id", name="uq_event_outbox_event_id"),
        sa.UniqueConstraint("dedup_key", name="uq_event_outbox_dedup_key"),
        schema="core",
    )
    op.create_index("ix_event_outbox_type", "event_outbox", ["type"], schema="core")


def downgrade() -> None:
    op.drop_table("event_outbox", schema="core")
