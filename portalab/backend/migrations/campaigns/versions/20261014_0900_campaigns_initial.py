"""campaigns schema — campaigns, versions, occurrences, activation log

Revision ID: campaigns_0001
Revises:
Create Date: 2026-10-14 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl
from portalab.core.extensions import create_extension_ddl

revision: str = "campaigns_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("campaigns",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
TABLES = (
    "open_intervals",
    "activation_log",
    "versions",
    "overrides",
    "occurrences",
    "campaigns",
    "attribute_failures",
)


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "campaigns"')
    op.execute(create_extension_ddl("btree_gist"))  # exclusion constraint on activation intervals
    op.create_table(
        "attribute_failures",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("day", "event_type", name="pk_attribute_failures"),
        schema="campaigns",
    )
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("archived_at", TZ, nullable=True),
        sa.CheckConstraint(
            "state IN ('draft', 'scheduled', 'active', 'paused', 'ended', 'archived')",
            name="ck_campaigns_state",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_campaigns"),
        sa.UniqueConstraint("key", name="uq_campaigns_key"),
        _user_fk("campaigns", "created_by", "SET NULL"),
        schema="campaigns",
    )
    op.create_table(
        "occurrences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("start_at", TZ, nullable=False),
        sa.Column("end_at", TZ, nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.CheckConstraint(
            "status IN ('planned', 'active', 'ended', 'skipped', 'cancelled')", name="ck_occurrences_status"
        ),
        sa.CheckConstraint("end_at > start_at", name="ck_occurrences_window"),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.campaigns.id"],
            name="fk_occurrences_campaign_id_campaigns",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_occurrences"),
        sa.UniqueConstraint("campaign_id", "index", name="uq_occurrences_index"),
        schema="campaigns",
    )
    op.create_index(
        "ix_occurrences_window", "occurrences", ["start_at", "end_at"], unique=False, schema="campaigns"
    )
    op.create_table(
        "overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("from_at", TZ, nullable=False),
        sa.Column("until_at", TZ, nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("expired_at", TZ, nullable=True),
        sa.CheckConstraint("kind IN ('activate', 'deactivate')", name="ck_overrides_kind"),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.campaigns.id"], name="fk_overrides_campaign_id_campaigns"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_overrides"),
        _user_fk("overrides", "actor_user_id", "SET NULL"),
        schema="campaigns",
    )
    op.create_index(
        "ix_overrides_campaign", "overrides", ["campaign_id", "from_at"], unique=False, schema="campaigns"
    )
    op.create_table(
        "versions",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_from", TZ, nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.campaigns.id"], name="fk_versions_campaign_id_campaigns"
        ),
        sa.PrimaryKeyConstraint("campaign_id", "version", name="pk_versions"),
        schema="campaigns",
        info={"portalab_append_only": True},
    )
    op.create_table(
        "activation_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("occurrence_id", sa.Uuid(), nullable=True),
        sa.Column("during", postgresql.TSTZRANGE(), nullable=False),
        sa.Column("cause", sa.String(length=10), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=True),
        postgresql.ExcludeConstraint(
            (sa.column("campaign_id"), "="),
            (sa.column("during"), "&&"),
            using="gist",
            name="ex_activation_log_overlap",
        ),
        sa.CheckConstraint("cause IN ('schedule', 'manual')", name="ck_activation_log_cause"),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.campaigns.id"], name="fk_activation_log_campaign_id_campaigns"
        ),
        sa.ForeignKeyConstraint(
            ["occurrence_id"],
            ["campaigns.occurrences.id"],
            name="fk_activation_log_occurrence_id_occurrences",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_activation_log"),
        schema="campaigns",
        info={"portalab_append_only": True},
    )
    op.create_table(
        "open_intervals",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("opened_at", TZ, nullable=False),
        sa.Column("cause", sa.String(length=10), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("occurrence_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.CheckConstraint("cause IN ('schedule', 'manual')", name="ck_open_intervals_cause"),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.campaigns.id"], name="fk_open_intervals_campaign_id_campaigns"
        ),
        sa.ForeignKeyConstraint(
            ["occurrence_id"],
            ["campaigns.occurrences.id"],
            name="fk_open_intervals_occurrence_id_occurrences",
        ),
        sa.PrimaryKeyConstraint("campaign_id", name="pk_open_intervals"),
        schema="campaigns",
    )
    for table in ("versions", "activation_log"):
        for statement in append_only_ddl("campaigns", table):
            op.execute(statement)


def downgrade() -> None:
    for table in ("versions", "activation_log"):
        for statement in drop_append_only_ddl("campaigns", table):
            op.execute(statement)
    for table in TABLES:
        op.drop_table(table, schema="campaigns")
    op.execute('DROP SCHEMA IF EXISTS "campaigns"')
