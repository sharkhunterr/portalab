"""support schema — Slice A: incidents, affected services, append-only update timeline, evidence pointers
(spec 016 T007). Ticket and feedback tables arrive with Slice B in a second revision.

Revision ID: support_0001
Revises:
Create Date: 2026-10-06 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "support_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("support",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
STATES = "state IN ('investigating', 'identified', 'monitoring', 'resolved')"


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "support"')
    op.execute("CREATE SEQUENCE support.incident_number_seq")
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("dedup_key", sa.String(160)),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.Column("resolved_at", TZ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_incidents"),
        sa.UniqueConstraint("source", "dedup_key", name="uq_incidents_source_dedup"),
        sa.UniqueConstraint("number", name="uq_incidents_number"),
        sa.CheckConstraint("severity IN ('minor', 'major', 'critical')", name="ck_incidents_severity"),
        sa.CheckConstraint(STATES, name="ck_incidents_state"),
        sa.CheckConstraint(
            "source IN ('manual', 'observability', 'health', 'automation')", name="ck_incidents_source"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["identity.users.id"], name="fk_incidents_created_by_users", ondelete="SET NULL"
        ),
        schema="support",
    )
    op.create_table(
        "incident_services",
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("incident_id", "service_id", name="pk_incident_services"),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["support.incidents.id"],
            name="fk_incident_services_incident_id_incidents",
            ondelete="CASCADE",
        ),
        schema="support",
    )
    op.create_table(
        "incident_updates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("update_seq", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("author_user_id", sa.Uuid()),
        sa.Column("created_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_incident_updates"),
        sa.UniqueConstraint("incident_id", "update_seq", name="uq_incident_updates_seq"),
        sa.CheckConstraint(STATES, name="ck_incident_updates_state"),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["support.incidents.id"], name="fk_incident_updates_incident_id_incidents"
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"], ["identity.users.id"], name="fk_incident_updates_author_user_id_users"
        ),
        schema="support",
    )
    for statement in append_only_ddl("support", "incident_updates"):
        op.execute(statement)
    op.create_table(
        "incident_evidence",
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_ref", sa.String(200), nullable=False),
        sa.Column("added_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("incident_id", "evidence_ref", name="pk_incident_evidence"),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["support.incidents.id"],
            name="fk_incident_evidence_incident_id_incidents",
            ondelete="CASCADE",
        ),
        schema="support",
    )


def downgrade() -> None:
    op.drop_table("incident_evidence", schema="support")
    for statement in drop_append_only_ddl("support", "incident_updates"):
        op.execute(statement)
    op.drop_table("incident_updates", schema="support")
    op.drop_table("incident_services", schema="support")
    op.drop_table("incidents", schema="support")
    op.execute("DROP SEQUENCE IF EXISTS support.incident_number_seq")
