"""identity schema — the session's active household profile (spec 032)

Revision ID: identity_0006
Revises: identity_0005
Create Date: 2026-11-14 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "identity_0006"
down_revision: str | Sequence[str] | None = "identity_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # the session's active household profile (the households themselves: the household schema, household_0001)
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
