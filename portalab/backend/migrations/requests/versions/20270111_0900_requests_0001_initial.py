"""requests schema — the titles members ask the administrators for, and the members who want them
(issue 363)

Revision ID: requests_0001
Revises:
Create Date: 2026-11-06 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "requests_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("requests",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)
OPEN = "status IN ('new', 'accepted', 'in_progress')"


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "requests"')
    op.create_table(
        "requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("folded", sa.String(300), nullable=False),
        sa.Column("creators", postgresql.JSONB(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("ids", postgresql.JSONB(), nullable=False),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("requester_id", sa.Uuid(), nullable=True),
        sa.Column("object_id", sa.Uuid(), nullable=True),
        sa.Column("spend_id", sa.Uuid(), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_requests"),
        sa.ForeignKeyConstraint(
            ["requester_id"], ["identity.users.id"], name="fk_requests_requester_id", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["identity.users.id"], name="fk_requests_decided_by", ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "status IN ('new', 'accepted', 'in_progress', 'available', 'refused', 'cancelled')",
            name="ck_requests_status",
        ),
        schema="requests",
    )
    op.create_index("ix_requests_status_updated", "requests", ["status", "updated_at"], schema="requests")
    op.create_index(
        "ix_requests_open_title",
        "requests",
        ["kind", "folded"],
        schema="requests",
        postgresql_where=sa.text(OPEN),
    )
    op.create_table(
        "supporters",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("asked", sa.Boolean(), nullable=False),
        sa.Column("since", TZ, nullable=False),
        sa.PrimaryKeyConstraint("request_id", "user_id", name="pk_supporters"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["requests.requests.id"], name="fk_supporters_request_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_supporters_user_id", ondelete="CASCADE"
        ),
        schema="requests",
    )
    op.create_index("ix_supporters_user", "supporters", ["user_id", "since"], schema="requests")


def downgrade() -> None:
    op.execute('DROP SCHEMA IF EXISTS "requests" CASCADE')
