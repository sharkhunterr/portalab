"""media schema — raw activity history, ingestion cursors, daily aggregates and object metadata (027)

Revision ID: media_0002
Revises: media_0001
Create Date: 2026-10-20 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "media_0002"
down_revision: str | Sequence[str] | None = "media_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "activity_cursors",
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=12), nullable=False),
        sa.Column("mode", sa.String(length=12), nullable=False),
        sa.Column("cursor", sa.String(length=200), nullable=True),
        sa.Column("watermark", TZ, nullable=True),
        sa.Column("items", sa.BigInteger(), nullable=False),
        sa.Column("backfilled_at", TZ, nullable=True),
        sa.Column("last_run_at", TZ, nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.CheckConstraint("mode IN ('backfill', 'incremental')", name="ck_activity_cursors_mode"),
        sa.PrimaryKeyConstraint("service_id", name="pk_activity_cursors"),
        schema="media",
    )
    op.create_table(
        "activity_daily",
        sa.Column("day", TZ, nullable=False),
        sa.Column("user_key", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("plays", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Integer(), nullable=False),
        sa.Column("seconds", sa.Float(), nullable=False),
        sa.Column("works", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("day", "user_key", "kind", name="pk_activity_daily"),
        schema="media",
    )
    op.create_index("ix_activity_daily_user", "activity_daily", ["user_key", "day"], schema="media")
    op.create_table(
        "activity_dirty_days",
        sa.Column("day", TZ, nullable=False),
        sa.PrimaryKeyConstraint("day", name="pk_activity_dirty_days"),
        schema="media",
    )
    op.create_table(
        "activity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("ref", sa.String(length=200), nullable=False),
        sa.Column("family", sa.String(length=40), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("counted", sa.Boolean(), nullable=False),
        sa.Column("external_user_id", sa.String(length=200), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("parent_title", sa.String(length=500), nullable=True),
        sa.Column("object_id", sa.Uuid(), nullable=True),
        sa.Column("work_id", sa.Uuid(), nullable=True),
        sa.Column("item_external_id", sa.String(length=200), nullable=True),
        sa.Column("ids", postgresql.JSONB(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("stopped_at", TZ, nullable=True),
        sa.Column("watched_s", sa.Float(), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("device", sa.String(length=120), nullable=True),
        sa.Column("platform", sa.String(length=60), nullable=True),
        sa.Column("received_at", TZ, nullable=False),
        sa.CheckConstraint(
            "kind IN ('movie', 'episode', 'live', 'track', 'book', 'audiobook', 'other')",
            name="ck_activity_kind",
        ),
        sa.ForeignKeyConstraint(
            ["object_id"], ["media.objects.id"], name="fk_activity_object_id_objects", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["media.objects.id"], name="fk_activity_work_id_objects", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_activity_user_id_users", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_activity"),
        sa.UniqueConstraint("service_id", "ref", name="uq_activity_service_ref"),
        schema="media",
    )
    op.create_index(
        "ix_activity_external_user", "activity", ["service_id", "external_user_id"], schema="media"
    )
    op.create_index("ix_activity_family", "activity", ["family", "priority", "started_at"], schema="media")
    op.create_index("ix_activity_started", "activity", ["started_at"], schema="media")
    op.create_index("ix_activity_user", "activity", ["user_id", "started_at"], schema="media")
    op.create_index("ix_activity_work", "activity", ["work_id", "started_at"], schema="media")
    op.create_table(
        "object_metadata",
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("fetched_at", TZ, nullable=False),
        sa.CheckConstraint("status IN ('found', 'missing', 'error')", name="ck_object_metadata_status"),
        sa.ForeignKeyConstraint(
            ["object_id"],
            ["media.objects.id"],
            name="fk_object_metadata_object_id_objects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("object_id", name="pk_object_metadata"),
        schema="media",
    )
    op.create_index("ix_object_metadata_fetched", "object_metadata", ["status", "fetched_at"], schema="media")


def downgrade() -> None:
    op.drop_table("object_metadata", schema="media")
    op.drop_table("activity", schema="media")
    op.drop_table("activity_dirty_days", schema="media")
    op.drop_table("activity_daily", schema="media")
    op.drop_table("activity_cursors", schema="media")
