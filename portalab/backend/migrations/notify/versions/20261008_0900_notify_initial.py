"""notify schema — categories mirror, communications, notification center, deliveries, e-mail outbox,
maintenance reminders, digest state (spec 010 T007)

Revision ID: notify_0001
Revises:
Create Date: 2026-10-08 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "notify_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("notify",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)


def _user_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["user_id"], ["identity.users.id"], name=f"fk_{table}_user_id_users", ondelete="CASCADE"
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "notify"')
    op.create_table(
        "categories",
        sa.Column("key", sa.String(96), nullable=False),
        sa.Column("owner", sa.String(80), nullable=False),
        sa.Column("label_key", sa.String(128), nullable=False),
        sa.Column("default_priority", sa.String(10), nullable=False),
        sa.Column("default_channels", postgresql.JSONB(), nullable=False),
        sa.Column("mandatory_channels", postgresql.JSONB(), nullable=False),
        sa.Column("user_mutable", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_categories"),
        schema="notify",
    )
    op.create_table(
        "communications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("category", sa.String(96), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("source_ref", sa.String(160)),
        sa.Column("dedup_key", sa.String(200), nullable=False),
        sa.Column("template_key", sa.String(128), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("subject_ref", sa.String(160)),
        sa.Column("audience_spec", postgresql.JSONB(), nullable=False),
        sa.Column("required_permission", sa.String(128)),
        sa.Column("produced_by", sa.String(80), nullable=False),
        sa.Column("valid_until", TZ),
        sa.Column("action_url", sa.String(256)),
        sa.Column("recipients", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_communications"),
        sa.UniqueConstraint("source", "dedup_key", name="uq_communications_source_dedup"),
        sa.CheckConstraint("kind IN ('notification', 'alert')", name="ck_communications_kind"),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'critical')", name="ck_communications_priority"
        ),
        sa.CheckConstraint(
            "kind = 'notification' OR priority IN ('high', 'critical')",
            name="ck_communications_alert_priority",
        ),
        schema="notify",
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("communication_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("language", sa.String(35), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("category", sa.String(96), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("priority_rank", sa.Integer(), nullable=False),
        sa.Column("subject_ref", sa.String(160)),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("action_url", sa.String(256)),
        sa.Column("read_at", TZ),
        sa.Column("archived_at", TZ),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        sa.CheckConstraint("kind IN ('notification', 'alert')", name="ck_notifications_kind"),
        sa.ForeignKeyConstraint(
            ["communication_id"],
            ["notify.communications.id"],
            name="fk_notifications_communication_id_communications",
        ),
        _user_fk("notifications"),
        schema="notify",
    )
    op.create_index(
        "ix_notifications_inbox", "notifications", ["user_id", "archived_at", "created_at"], schema="notify"
    )
    op.create_table(
        "deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("communication_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("suppress_reason", sa.String(20)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(200)),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("sent_at", TZ),
        sa.PrimaryKeyConstraint("id", name="pk_deliveries"),
        sa.UniqueConstraint("communication_id", "user_id", "channel", name="uq_deliveries_recipient_channel"),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'delivered', 'failed', 'suppressed')", name="ck_deliveries_status"
        ),
        sa.ForeignKeyConstraint(
            ["communication_id"],
            ["notify.communications.id"],
            name="fk_deliveries_communication_id_communications",
        ),
        _user_fk("deliveries"),
        schema="notify",
    )
    op.create_table(
        "email_outbox",
        sa.Column("delivery_id", sa.Uuid(), nullable=False),
        sa.Column("to_hash", sa.String(64), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text()),
        sa.Column("next_attempt_at", TZ, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("delivery_id", name="pk_email_outbox"),
        sa.ForeignKeyConstraint(
            ["delivery_id"],
            ["notify.deliveries.id"],
            name="fk_email_outbox_delivery_id_deliveries",
            ondelete="CASCADE",
        ),
        schema="notify",
    )
    op.create_table(
        "maintenance_reminders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("maintenance_id", sa.String(64), nullable=False),
        sa.Column("schedule_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("service_id", sa.String(64)),
        sa.Column("run_at", TZ, nullable=False),
        sa.Column("valid_until", TZ, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("communication_id", sa.Uuid()),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_maintenance_reminders"),
        sa.UniqueConstraint("maintenance_id", "schedule_version", "kind", name="uq_maintenance_reminders"),
        sa.CheckConstraint(
            "kind IN ('j1', 'h1', 'start', 'corrective')", name="ck_maintenance_reminders_kind"
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'sent', 'cancelled', 'expired')", name="ck_maintenance_reminders_status"
        ),
        schema="notify",
    )
    op.create_table(
        "digest_state",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("last_digest_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_digest_state"),
        _user_fk("digest_state"),
        schema="notify",
    )


def downgrade() -> None:
    for name in ("digest_state", "maintenance_reminders", "email_outbox", "deliveries"):
        op.drop_table(name, schema="notify")
    op.drop_index("ix_notifications_inbox", table_name="notifications", schema="notify")
    for name in ("notifications", "communications", "categories"):
        op.drop_table(name, schema="notify")
