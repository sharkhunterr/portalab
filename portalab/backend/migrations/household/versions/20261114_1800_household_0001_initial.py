"""household schema — households: a member account's profiles and their access requests (spec 032).

The first builds kept them in the identity schema: they move here with their rows.

Revision ID: household_0001
Revises:
Create Date: 2026-11-14 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "household_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("household",)
depends_on: str | Sequence[str] | None = ("identity_0006",)

TZ = sa.DateTime(timezone=True)
USERS = "identity.users.id"
# the first builds' names → the household schema's
RENAMED = (
    ("pk_household_members", "pk_members"),
    ("ck_household_members_kind", "ck_members_kind"),
    ("ck_household_members_owner", "ck_members_owner"),
    ("fk_household_members_user_id_users", "fk_members_user_id_users"),
    ("fk_household_members_owner_id_users", "fk_members_owner_id_users"),
)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "household"')
    moved = op.get_bind().scalar(sa.text("SELECT to_regclass('identity.household_members') IS NOT NULL"))
    if moved:
        op.execute("ALTER TABLE identity.household_members SET SCHEMA household")
        op.execute("ALTER TABLE household.household_members RENAME TO members")
        for old, new in RENAMED:
            op.execute(f"ALTER TABLE household.members RENAME CONSTRAINT {old} TO {new}")
        op.execute("ALTER INDEX household.ix_household_members_owner_id RENAME TO ix_members_owner_id")
        op.execute("ALTER TABLE identity.access_requests SET SCHEMA household")
        return
    op.create_table(
        "members",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("color", sa.String(16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("pin_hash", sa.String(512), nullable=True),
        sa.Column("community_visible", sa.Boolean(), nullable=False),
        sa.Column("restrictions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("kind IN ('owner', 'standard', 'child', 'custom')", name=op.f("ck_members_kind")),
        sa.CheckConstraint("(kind = 'owner') = (owner_id = user_id)", name=op.f("ck_members_owner")),
        sa.ForeignKeyConstraint(
            ["user_id"], [USERS], name=op.f("fk_members_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], [USERS], name=op.f("fk_members_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_members")),
        schema="household",
    )
    op.create_index("ix_members_owner_id", "members", ["owner_id", "position"], schema="household")
    op.create_table(
        "access_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("subject_ref", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("rating", sa.String(32), nullable=True),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("decided_at", TZ, nullable=True),
        sa.Column("expires_at", TZ, nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'denied')", name=op.f("ck_access_requests_status")
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], [USERS], name=op.f("fk_access_requests_profile_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], [USERS], name=op.f("fk_access_requests_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_access_requests")),
        schema="household",
    )
    op.create_index(
        "uq_access_requests_pending",
        "access_requests",
        ["profile_id", "kind", "subject_ref"],
        unique=True,
        schema="household",
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_access_requests_owner_id",
        "access_requests",
        ["owner_id", "status", "created_at"],
        schema="household",
    )


def downgrade() -> None:
    op.drop_table("access_requests", schema="household")
    op.drop_table("members", schema="household")
    op.execute('DROP SCHEMA IF EXISTS "household"')
