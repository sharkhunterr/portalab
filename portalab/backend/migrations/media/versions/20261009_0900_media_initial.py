"""media schema — catalog objects, external ids, source items, field candidates, tags, match candidates,
merge log, images, user links, playback sessions, history projection, progress, request quota and requests
(spec 024 T007)

Revision ID: media_0001
Revises:
Create Date: 2026-10-09 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "media_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("media",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
TABLES = (
    "images",
    "field_candidates",
    "user_progress",
    "source_items",
    "requests",
    "playback_sessions",
    "object_tags",
    "match_candidates",
    "history_entries",
    "external_ids",
    "user_links",
    "request_quota_units",
    "request_quota_ledger",
    "objects",
    "merge_log",
)


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "media"')
    op.create_table(
        "merge_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("other_id", sa.Uuid(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint("action IN ('merge', 'split')", name="ck_merge_log_action"),
        sa.PrimaryKeyConstraint("id", name="pk_merge_log"),
        schema="media",
    )
    op.create_table(
        "objects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("sort_title", sa.String(length=500), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("effective", postgresql.JSONB(), nullable=False),
        sa.Column("field_provenance", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("merged_into", sa.Uuid(), nullable=True),
        sa.Column("first_seen_at", TZ, nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("status IN ('active', 'hidden', 'merged')", name="ck_objects_status"),
        sa.ForeignKeyConstraint(["merged_into"], ["media.objects.id"], name="fk_objects_merged_into_objects"),
        sa.ForeignKeyConstraint(["parent_id"], ["media.objects.id"], name="fk_objects_parent_id_objects"),
        sa.PrimaryKeyConstraint("id", name="pk_objects"),
        schema="media",
    )
    op.create_index("ix_objects_kind_title", "objects", ["kind", "sort_title"], unique=False, schema="media")
    op.create_index("ix_objects_parent", "objects", ["parent_id", "position"], unique=False, schema="media")
    op.create_table(
        "request_quota_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("delta", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(length=12), nullable=False),
        sa.Column("source_ref", sa.String(length=200), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint(
            "reason IN ('purchase', 'refund', 'consumption', 'admin')", name="ck_request_quota_ledger_reason"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_request_quota_ledger"),
        sa.UniqueConstraint("idempotency_key", name="uq_request_quota_ledger_idempotency"),
        _user_fk("request_quota_ledger", "user_id", "CASCADE"),
        schema="media",
    )
    op.create_table(
        "request_quota_units",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("units_remaining", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("units_remaining >= 0", name="ck_request_quota_units_units_remaining"),
        sa.PrimaryKeyConstraint("user_id", name="pk_request_quota_units"),
        _user_fk("request_quota_units", "user_id", "CASCADE"),
        schema="media",
    )
    op.create_table(
        "user_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("external_user_id", sa.String(length=200), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_user_links"),
        sa.UniqueConstraint("service_id", "external_user_id", name="uq_user_links_external"),
        sa.UniqueConstraint("user_id", "service_id", name="uq_user_links_user_service"),
        _user_fk("user_links", "user_id", "CASCADE"),
        schema="media",
    )
    op.create_table(
        "external_ids",
        sa.Column("scheme", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["object_id"], ["media.objects.id"], name="fk_external_ids_object_id_objects"
        ),
        sa.PrimaryKeyConstraint("scheme", "value", name="pk_external_ids"),
        schema="media",
    )
    op.create_index("ix_external_ids_object", "external_ids", ["object_id"], unique=False, schema="media")
    op.create_table(
        "history_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("session_key", sa.String(length=300), nullable=True),
        sa.Column("position_from_s", sa.Float(), nullable=False),
        sa.Column("position_to_s", sa.Float(), nullable=False),
        sa.Column("consumed_s", sa.Float(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.Column("received_at", TZ, nullable=False),
        sa.CheckConstraint("kind IN ('session', 'progress', 'finished')", name="ck_history_entries_kind"),
        sa.ForeignKeyConstraint(
            ["object_id"], ["media.objects.id"], name="fk_history_entries_object_id_objects"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_history_entries"),
        sa.UniqueConstraint("event_id", name="uq_history_entries_event"),
        _user_fk("history_entries", "user_id", "CASCADE"),
        schema="media",
    )
    op.create_index(
        "ix_history_entries_object",
        "history_entries",
        ["object_id", "occurred_at"],
        unique=False,
        schema="media",
    )
    op.create_index(
        "ix_history_entries_user", "history_entries", ["user_id", "occurred_at"], unique=False, schema="media"
    )
    op.create_table(
        "match_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("object_a", sa.Uuid(), nullable=False),
        sa.Column("object_b", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("decided_at", TZ, nullable=True),
        sa.CheckConstraint("state IN ('proposed', 'accepted', 'rejected')", name="ck_match_candidates_state"),
        sa.ForeignKeyConstraint(
            ["object_a"], ["media.objects.id"], name="fk_match_candidates_object_a_objects"
        ),
        sa.ForeignKeyConstraint(
            ["object_b"], ["media.objects.id"], name="fk_match_candidates_object_b_objects"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_candidates"),
        sa.UniqueConstraint("object_a", "object_b", name="uq_match_candidates_pair"),
        schema="media",
    )
    op.create_table(
        "object_tags",
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("tag_kind", sa.String(length=10), nullable=False),
        sa.Column("value", sa.String(length=120), nullable=False),
        sa.CheckConstraint(
            "tag_kind IN ('genre', 'tag', 'keyword', 'person')", name="ck_object_tags_tag_kind"
        ),
        sa.ForeignKeyConstraint(["object_id"], ["media.objects.id"], name="fk_object_tags_object_id_objects"),
        sa.PrimaryKeyConstraint("object_id", "tag_kind", "value", name="pk_object_tags"),
        schema="media",
    )
    op.create_index(
        "ix_object_tags_value", "object_tags", ["tag_kind", "value"], unique=False, schema="media"
    )
    op.create_table(
        "playback_sessions",
        sa.Column("session_key", sa.String(length=300), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("external_user_id", sa.String(length=200), nullable=True),
        sa.Column("object_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("position_s", sa.Float(), nullable=False),
        sa.Column("max_position_s", sa.Float(), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("device", sa.String(length=120), nullable=True),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.Column("as_of", TZ, nullable=False),
        sa.Column("last_event_at", TZ, nullable=False),
        sa.Column("state_seq", sa.Integer(), nullable=False),
        sa.Column("ended", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "state IN ('playing', 'paused', 'buffering', 'stopped', 'stale', 'interrupted')",
            name="ck_playback_sessions_state",
        ),
        sa.ForeignKeyConstraint(
            ["object_id"], ["media.objects.id"], name="fk_playback_sessions_object_id_objects"
        ),
        sa.PrimaryKeyConstraint("session_key", name="pk_playback_sessions"),
        _user_fk("playback_sessions", "user_id", "CASCADE"),
        schema="media",
    )
    op.create_index(
        "ix_playback_sessions_user",
        "playback_sessions",
        ["user_id", "updated_at"],
        unique=False,
        schema="media",
    )
    op.create_table(
        "requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=True),
        sa.Column("external_ref", postgresql.JSONB(), nullable=False),
        sa.Column("requester_user_id", sa.Uuid(), nullable=True),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("external_request_id", sa.String(length=200), nullable=True),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("source_state", sa.String(length=60), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("counted", sa.String(length=10), nullable=False),
        sa.Column("requested_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint(
            "state IN ('pending', 'approved', 'declined', 'processing', 'available', 'failed', 'cancelled')",
            name="ck_requests_state",
        ),
        sa.ForeignKeyConstraint(["object_id"], ["media.objects.id"], name="fk_requests_object_id_objects"),
        sa.PrimaryKeyConstraint("id", name="pk_requests"),
        sa.UniqueConstraint("idempotency_key", name="uq_requests_idempotency"),
        sa.UniqueConstraint("service_id", "external_request_id", name="uq_requests_service_external"),
        _user_fk("requests", "requester_user_id", "SET NULL"),
        schema="media",
    )
    op.create_index(
        "ix_requests_requester",
        "requests",
        ["requester_user_id", "requested_at"],
        unique=False,
        schema="media",
    )
    op.create_table(
        "source_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=True),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("availability", sa.String(length=12), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("observed_at", TZ, nullable=False),
        sa.Column("first_seen_at", TZ, nullable=False),
        sa.Column("last_seen_at", TZ, nullable=False),
        sa.CheckConstraint(
            "availability IN ('available', 'unavailable', 'unknown')", name="ck_source_items_availability"
        ),
        sa.ForeignKeyConstraint(
            ["object_id"], ["media.objects.id"], name="fk_source_items_object_id_objects"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_items"),
        sa.UniqueConstraint("service_id", "external_id", name="uq_source_items_service_external"),
        schema="media",
    )
    op.create_index("ix_source_items_object", "source_items", ["object_id"], unique=False, schema="media")
    op.create_table(
        "user_progress",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("resume_position_s", sa.Float(), nullable=False),
        sa.Column("percent", sa.Float(), nullable=False),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("last_occurred_at", TZ, nullable=False),
        sa.Column("finished_at", TZ, nullable=True),
        sa.CheckConstraint("state IN ('in_progress', 'finished')", name="ck_user_progress_state"),
        sa.ForeignKeyConstraint(
            ["object_id"], ["media.objects.id"], name="fk_user_progress_object_id_objects"
        ),
        sa.PrimaryKeyConstraint("user_id", "object_id", name="pk_user_progress"),
        _user_fk("user_progress", "user_id", "CASCADE"),
        schema="media",
    )
    op.create_table(
        "field_candidates",
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("field", sa.String(length=40), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("source_item_id", sa.Uuid(), nullable=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("observed_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["object_id"], ["media.objects.id"], name="fk_field_candidates_object_id_objects"
        ),
        sa.ForeignKeyConstraint(
            ["source_item_id"],
            ["media.source_items.id"],
            name="fk_field_candidates_source_item_id_source_items",
        ),
        sa.PrimaryKeyConstraint("object_id", "field", "source_system", name="pk_field_candidates"),
        schema="media",
    )
    op.create_table(
        "images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("blob_key", sa.String(length=200), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.String(length=300), nullable=False),
        sa.Column("source_item_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint("role IN ('poster', 'backdrop', 'thumb')", name="ck_images_role"),
        sa.ForeignKeyConstraint(["object_id"], ["media.objects.id"], name="fk_images_object_id_objects"),
        sa.ForeignKeyConstraint(
            ["source_item_id"], ["media.source_items.id"], name="fk_images_source_item_id_source_items"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_images"),
        sa.UniqueConstraint("object_id", "role", name="uq_images_object_role"),
        schema="media",
    )
    for statement in append_only_ddl("media", "merge_log"):
        op.execute(statement)


def downgrade() -> None:
    for statement in drop_append_only_ddl("media", "merge_log"):
        op.execute(statement)
    for table in TABLES:
        op.drop_table(table, schema="media")
    op.execute('DROP SCHEMA IF EXISTS "media"')
