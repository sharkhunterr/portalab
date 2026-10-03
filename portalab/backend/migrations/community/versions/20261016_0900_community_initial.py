"""community schema — feed entries, community events, visibility preferences

Revision ID: community_0001
Revises:
Create Date: 2026-10-16 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "community_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("community",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
TABLES = ("visibility_preferences", "feed_entries", "events")


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "community"')
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description_md", sa.Text(), nullable=False),
        sa.Column("rendered_html", sa.Text(), nullable=False),
        sa.Column("starts_at", TZ, nullable=False),
        sa.Column("ends_at", TZ, nullable=True),
        sa.Column("all_day", sa.Boolean(), nullable=False),
        sa.Column("reference_tz", sa.String(length=64), nullable=False),
        sa.Column("audience", sa.String(length=10), nullable=False),
        sa.Column("audience_roles", postgresql.JSONB(), nullable=False),
        sa.Column("organizer_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("audience IN ('public', 'community', 'roles')", name="ck_events_audience"),
        sa.CheckConstraint("status IN ('scheduled', 'cancelled')", name="ck_events_status"),
        sa.PrimaryKeyConstraint("id", name="pk_events"),
        _user_fk("events", "organizer_id", "SET NULL"),
        schema="community",
    )
    op.create_index("ix_events_window", "events", ["starts_at"], unique=False, schema="community")
    op.create_table(
        "feed_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_event_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=128), nullable=False),
        sa.Column("subject_ref", sa.String(length=200), nullable=True),
        sa.Column("text_key", sa.String(length=160), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("visibility_class", sa.String(length=10), nullable=False),
        sa.Column("occurred_at", TZ, nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint(
            "visibility_class IN ('public', 'community')", name="ck_feed_entries_visibility_class"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feed_entries"),
        sa.UniqueConstraint("source_event_id", name="uq_feed_entries_source_event_id"),
        _user_fk("feed_entries", "actor_user_id", "CASCADE"),
        schema="community",
    )
    op.create_index(
        "ix_feed_entries_actor",
        "feed_entries",
        ["actor_user_id", "occurred_at"],
        unique=False,
        schema="community",
    )
    op.create_index("ix_feed_entries_time", "feed_entries", ["occurred_at"], unique=False, schema="community")
    op.create_table(
        "visibility_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("datum_class", sa.String(length=40), nullable=False),
        sa.Column("level", sa.String(length=12), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint(
            "level IN ('public', 'community', 'leaderboard', 'private')",
            name="ck_visibility_preferences_level",
        ),
        sa.PrimaryKeyConstraint("user_id", "datum_class", name="pk_visibility_preferences"),
        _user_fk("visibility_preferences", "user_id", "CASCADE"),
        schema="community",
    )


def downgrade() -> None:
    for table in TABLES:
        op.drop_table(table, schema="community")
    op.execute('DROP SCHEMA IF EXISTS "community"')
