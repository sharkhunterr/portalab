"""identity schema — households: a member account's profiles, the session's active profile, access requests
(spec 032)

Revision ID: identity_0006
Revises: identity_0005
Create Date: 2026-11-14 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "identity_0006"
down_revision: str | Sequence[str] | None = "identity_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)
USERS = "identity.users.id"


def upgrade() -> None:
    op.create_table(
        "household_members",
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
        sa.CheckConstraint(
            "kind IN ('owner', 'standard', 'child', 'custom')", name=op.f("ck_household_members_kind")
        ),
        sa.CheckConstraint(
            "(kind = 'owner') = (owner_id = user_id)", name=op.f("ck_household_members_owner")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], [USERS], name=op.f("fk_household_members_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], [USERS], name=op.f("fk_household_members_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_household_members")),
        schema="identity",
    )
    op.create_index(
        "ix_household_members_owner_id", "household_members", ["owner_id", "position"], schema="identity"
    )
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
        schema="identity",
    )
    op.create_index(
        "uq_access_requests_pending",
        "access_requests",
        ["profile_id", "kind", "subject_ref"],
        unique=True,
        schema="identity",
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_access_requests_owner_id",
        "access_requests",
        ["owner_id", "status", "created_at"],
        schema="identity",
    )
    op.add_column("sessions", sa.Column("acting_user_id", sa.Uuid(), nullable=True), schema="identity")
    op.add_column(
        "sessions",
        sa.Column("profile_chosen", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="identity",
    )
    op.create_foreign_key(
        op.f("fk_sessions_acting_user_id_users"),
        "sessions",
        "users",
        ["acting_user_id"],
        ["id"],
        source_schema="identity",
        referent_schema="identity",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_sessions_acting_user_id_users"), "sessions", schema="identity", type_="foreignkey"
    )
    op.drop_column("sessions", "profile_chosen", schema="identity")
    op.drop_column("sessions", "acting_user_id", schema="identity")
    op.drop_index("ix_access_requests_owner_id", table_name="access_requests", schema="identity")
    op.drop_index("uq_access_requests_pending", table_name="access_requests", schema="identity")
    op.drop_table("access_requests", schema="identity")
    op.drop_index("ix_household_members_owner_id", table_name="household_members", schema="identity")
    op.drop_table("household_members", schema="identity")
