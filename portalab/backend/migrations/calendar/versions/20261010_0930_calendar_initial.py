"""calendar schema — reminders (spec 011 T009)

Revision ID: calendar_0001
Revises:
Create Date: 2026-10-10 09:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "calendar_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("calendar",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
TABLES = ("reminders",)


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.users.id"], name=f"fk_{table}_{column}_users", ondelete=ondelete
    )


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "calendar"')
    op.create_table(
        "reminders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=200), nullable=False),
        sa.Column("lead_minutes", sa.Integer(), nullable=False),
        sa.Column("remind_at", TZ, nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("last_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint(
            "status IN ('scheduled', 'sent', 'cancelled', 'stale')", name="ck_reminders_status"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reminders"),
        sa.UniqueConstraint(
            "user_id", "source_kind", "source_id", "lead_minutes", name="uq_reminders_item_lead"
        ),
        _user_fk("reminders", "user_id", "CASCADE"),
        schema="calendar",
    )
    op.create_index(
        "ix_reminders_user", "reminders", ["user_id", "remind_at"], unique=False, schema="calendar"
    )


def downgrade() -> None:
    for table in TABLES:
        op.drop_table(table, schema="calendar")
    op.execute('DROP SCHEMA IF EXISTS "calendar"')
