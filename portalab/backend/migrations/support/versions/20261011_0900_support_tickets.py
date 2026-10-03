"""support schema — tickets, workflows, attachments, drafts, diagnosis runs, feedback (spec 016 Slice B)

Revision ID: support_0002
Revises: support_0001
Create Date: 2026-10-11 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "support_0002"
down_revision: str | Sequence[str] | None = "support_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)
# The ticket history is append-only: only an erased actor may be tombstoned (actor_id -> NULL).
HISTORY_GUARD = """
CREATE OR REPLACE FUNCTION support.protect_ticket_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'support.ticket_history is append-only';
    END IF;
    IF (NEW.ticket_id, NEW.seq, NEW.kind, NEW.data, NEW.created_at)
         IS DISTINCT FROM (OLD.ticket_id, OLD.seq, OLD.kind, OLD.data, OLD.created_at)
       OR (NEW.actor_id IS DISTINCT FROM OLD.actor_id AND NEW.actor_id IS NOT NULL) THEN
        RAISE EXCEPTION 'support.ticket_history is append-only';
    END IF;
    RETURN NEW;
END $$
"""
HISTORY_TRIGGER = """
CREATE TRIGGER ticket_history_append_only BEFORE UPDATE OR DELETE ON support.ticket_history
FOR EACH ROW EXECUTE FUNCTION support.protect_ticket_history()
"""
TABLES = (
    "attachments",
    "ticket_tags",
    "ticket_history",
    "ticket_comments",
    "tickets",
    "feedback_conversions",
    "workflows",
    "ticket_types",
    "ticket_drafts",
    "feedback_items",
    "feedback_forms",
    "diagnosis_runs",
)


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.create_table(
        "diagnosis_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("steps", postgresql.JSONB(), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint(
            "outcome IN ('running', 'resolved', 'ticket_prefilled', 'inconclusive', 'failed')",
            name="ck_diagnosis_runs_outcome",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_diagnosis_runs"),
        _user_fk("diagnosis_runs", "user_id", "CASCADE"),
        schema="support",
    )
    op.create_table(
        "feedback_forms",
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_feedback_forms"),
        schema="support",
    )
    op.create_table(
        "feedback_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("form_key", sa.String(length=60), nullable=False),
        sa.Column("form_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("submitter_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint(
            "status IN ('new', 'reviewed', 'converted', 'dismissed')", name="ck_feedback_items_status"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feedback_items"),
        _user_fk("feedback_items", "submitter_id", "SET NULL"),
        schema="support",
    )
    op.create_index(
        "ix_feedback_items_status", "feedback_items", ["status", "created_at"], unique=False, schema="support"
    )
    op.create_table(
        "ticket_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("diagnosis_run_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ticket_drafts"),
        _user_fk("ticket_drafts", "user_id", "CASCADE"),
        schema="support",
    )
    op.create_table(
        "ticket_types",
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("workflow_key", sa.String(length=60), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_ticket_types"),
        schema="support",
    )
    op.create_table(
        "workflows",
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("key", "version", name="pk_workflows"),
        schema="support",
        info={"portalab_append_only": True},
    )
    op.create_table(
        "feedback_conversions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("feedback_id", sa.Uuid(), nullable=False),
        sa.Column("target_kind", sa.String(length=20), nullable=False),
        sa.Column("target_ref", sa.String(length=200), nullable=False),
        sa.Column("converted_by", sa.Uuid(), nullable=True),
        sa.Column("converted_at", TZ, nullable=False),
        sa.CheckConstraint(
            "target_kind IN ('ticket', 'contribution', 'feature_proposal', 'community_project')",
            name="ck_feedback_conversions_target_kind",
        ),
        sa.ForeignKeyConstraint(
            ["feedback_id"],
            ["support.feedback_items.id"],
            name="fk_feedback_conversions_feedback_id_feedback_items",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feedback_conversions"),
        sa.UniqueConstraint("feedback_id", "target_kind", name="uq_feedback_conversions_target"),
        schema="support",
        info={"portalab_append_only": True},
    )
    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("type_key", sa.String(length=60), nullable=False),
        sa.Column("workflow_key", sa.String(length=60), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requester_id", sa.Uuid(), nullable=True),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("priority", sa.String(length=8), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False),
        sa.Column("service_id", sa.String(length=64), nullable=True),
        sa.Column("incident_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("feedback_id", sa.Uuid(), nullable=True),
        sa.Column("technical_context", postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.Column("resolved_at", TZ, nullable=True),
        sa.Column("closed_at", TZ, nullable=True),
        sa.CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_tickets_priority"),
        sa.CheckConstraint(
            "source IN ('manual', 'ai_diagnosis', 'feedback_conversion', 'automation')",
            name="ck_tickets_source",
        ),
        sa.ForeignKeyConstraint(
            ["feedback_id"], ["support.feedback_items.id"], name="fk_tickets_feedback_id_feedback_items"
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["support.incidents.id"], name="fk_tickets_incident_id_incidents"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tickets"),
        sa.UniqueConstraint("number", name="uq_tickets_number"),
        _user_fk("tickets", "requester_id", "SET NULL"),
        _user_fk("tickets", "assignee_id", "SET NULL"),
        schema="support",
    )
    op.create_index("ix_tickets_incident", "tickets", ["incident_id"], unique=False, schema="support")
    op.create_index("ix_tickets_queue", "tickets", ["state", "updated_at"], unique=False, schema="support")
    op.create_index(
        "ix_tickets_requester", "tickets", ["requester_id", "created_at"], unique=False, schema="support"
    )
    op.create_table(
        "ticket_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("internal", sa.Boolean(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("edited_at", TZ, nullable=True),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["support.tickets.id"], name="fk_ticket_comments_ticket_id_tickets"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ticket_comments"),
        _user_fk("ticket_comments", "author_id", "SET NULL"),
        schema="support",
    )
    op.create_index(
        "ix_ticket_comments_ticket",
        "ticket_comments",
        ["ticket_id", "created_at"],
        unique=False,
        schema="support",
    )
    op.create_table(
        "ticket_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint(
            "kind IN ('created', 'transition', 'assignment', 'field_changed', 'tag', 'incident_linked', 'comment_added', 'attachment_added')",
            name="ck_ticket_history_kind",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["support.tickets.id"], name="fk_ticket_history_ticket_id_tickets"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ticket_history"),
        sa.UniqueConstraint("ticket_id", "seq", name="uq_ticket_history_seq"),
        schema="support",
    )
    op.create_table(
        "ticket_tags",
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("tag", sa.String(length=60), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["support.tickets.id"], name="fk_ticket_tags_ticket_id_tickets"
        ),
        sa.PrimaryKeyConstraint("ticket_id", "tag", name="pk_ticket_tags"),
        schema="support",
    )
    op.create_index("ix_ticket_tags_tag", "ticket_tags", ["tag"], unique=False, schema="support")
    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("blob_key", sa.String(length=200), nullable=False),
        sa.Column("filename", sa.String(length=120), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("private", sa.Boolean(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["comment_id"], ["support.ticket_comments.id"], name="fk_attachments_comment_id_ticket_comments"
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["support.tickets.id"], name="fk_attachments_ticket_id_tickets"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_attachments"),
        _user_fk("attachments", "uploaded_by", "SET NULL"),
        schema="support",
    )
    op.create_index("ix_attachments_ticket", "attachments", ["ticket_id"], unique=False, schema="support")
    op.execute("CREATE SEQUENCE IF NOT EXISTS support.ticket_number_seq START 1")
    for table in ("workflows", "feedback_conversions"):
        for statement in append_only_ddl("support", table):
            op.execute(statement)
    op.execute(HISTORY_GUARD)
    op.execute(HISTORY_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ticket_history_append_only ON support.ticket_history")
    op.execute("DROP FUNCTION IF EXISTS support.protect_ticket_history()")
    for table in ("workflows", "feedback_conversions"):
        for statement in drop_append_only_ddl("support", table):
            op.execute(statement)
    op.execute("DROP SEQUENCE IF EXISTS support.ticket_number_seq")
    for table in TABLES:
        op.drop_table(table, schema="support")
