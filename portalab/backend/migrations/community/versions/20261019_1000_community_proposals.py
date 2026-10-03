"""community schema — proposals, votes, participations, recognition and moderation logs (slice D)

Revision ID: community_0002
Revises: community_0001
Create Date: 2026-10-19 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "community_0002"
down_revision: str | Sequence[str] | None = "community_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)
TABLES = ("recognition_log", "votes", "vote_counts", "participations", "moderation_log", "proposals")
APPEND_ONLY = ("recognition_log", "moderation_log")


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.create_table(
        "proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("provenance_ref", sa.String(length=200), nullable=True),
        sa.Column("proposer_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("rendered_html", sa.Text(), nullable=False),
        sa.Column("renderer_version", sa.String(length=16), nullable=False),
        sa.Column("tags", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("help_wanted", sa.Boolean(), nullable=False),
        sa.Column("help_note", sa.String(length=500), nullable=True),
        sa.Column("lifecycle_ref", sa.String(length=64), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("kind IN ('project', 'feature')", name="ck_proposals_kind"),
        sa.CheckConstraint(
            "status IN ('pending_moderation', 'open', 'withdrawn', 'rejected')", name="ck_proposals_status"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_proposals"),
        sa.UniqueConstraint("provenance_ref", name="uq_proposals_provenance_ref"),
        _user_fk("proposals", "proposer_id", "SET NULL"),
        schema="community",
    )
    op.create_index("ix_proposals_proposer", "proposals", ["proposer_id"], unique=False, schema="community")
    op.create_index(
        "ix_proposals_status", "proposals", ["status", "created_at"], unique=False, schema="community"
    )
    op.create_table(
        "moderation_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("moderator_id", sa.Uuid(), nullable=True),
        sa.Column("decision", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint("decision IN ('approved', 'rejected')", name="ck_moderation_log_decision"),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["community.proposals.id"], name="fk_moderation_log_proposal_id_proposals"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_moderation_log"),
        _user_fk("moderation_log", "moderator_id", "RESTRICT"),
        schema="community",
        info={"portalab_append_only": True},
    )
    op.create_table(
        "participations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=12), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("recognized_at", TZ, nullable=True),
        sa.Column("recognized_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint("role IN ('contributor', 'tester', 'helper')", name="ck_participations_role"),
        sa.CheckConstraint("status IN ('active', 'withdrawn')", name="ck_participations_status"),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["community.proposals.id"], name="fk_participations_proposal_id_proposals"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_participations"),
        sa.UniqueConstraint("proposal_id", "user_id", "role", name="uq_participations"),
        _user_fk("participations", "user_id", "RESTRICT"),
        _user_fk("participations", "recognized_by", "SET NULL"),
        schema="community",
    )
    op.create_table(
        "vote_counts",
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["community.proposals.id"], name="fk_vote_counts_proposal_id_proposals"
        ),
        sa.PrimaryKeyConstraint("proposal_id", name="pk_vote_counts"),
        schema="community",
    )
    op.create_table(
        "votes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cast_at", TZ, nullable=False),
        sa.Column("retracted_at", TZ, nullable=True),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["community.proposals.id"], name="fk_votes_proposal_id_proposals"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_votes"),
        _user_fk("votes", "user_id", "CASCADE"),
        schema="community",
    )
    op.create_index(
        "uq_votes_active",
        "votes",
        ["proposal_id", "user_id"],
        unique=True,
        schema="community",
        postgresql_where=sa.text("retracted_at IS NULL"),
    )
    op.create_table(
        "recognition_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("participation_id", sa.Uuid(), nullable=False),
        sa.Column("recognizer_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["participation_id"],
            ["community.participations.id"],
            name="fk_recognition_log_participation_id_participations",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recognition_log"),
        _user_fk("recognition_log", "recognizer_id", "RESTRICT"),
        _user_fk("recognition_log", "recipient_id", "RESTRICT"),
        schema="community",
        info={"portalab_append_only": True},
    )
    op.create_index(
        "ix_recognition_log_recognizer",
        "recognition_log",
        ["recognizer_id", "created_at"],
        unique=False,
        schema="community",
    )
    for table in APPEND_ONLY:
        for statement in append_only_ddl("community", table):
            op.execute(statement)


def downgrade() -> None:
    for table in APPEND_ONLY:
        for statement in drop_append_only_ddl("community", table):
            op.execute(statement)
    for table in TABLES:
        op.drop_table(table, schema="community")
