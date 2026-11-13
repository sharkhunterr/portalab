"""identity schema — the second factor (TOTP), its recovery codes and the sign-ins waiting for it (issue 408)

Revision ID: identity_0005
Revises: identity_0004
Create Date: 2026-11-13 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "identity_0005"
down_revision: str | Sequence[str] | None = "identity_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)
USERS = "identity.users.id"


def upgrade() -> None:
    op.create_table(
        "totp_factors",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("secret", sa.String(512), nullable=False),
        sa.Column("confirmed_at", TZ, nullable=True),
        sa.Column("last_step", sa.BigInteger(), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], [USERS], name=op.f("fk_totp_factors_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_totp_factors")),
        schema="identity",
    )
    op.create_table(
        "recovery_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("used_at", TZ, nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], [USERS], name=op.f("fk_recovery_codes_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recovery_codes")),
        schema="identity",
    )
    op.create_index(op.f("ix_recovery_codes_user_id"), "recovery_codes", ["user_id"], schema="identity")
    op.create_table(
        "mfa_challenges",
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], [USERS], name=op.f("fk_mfa_challenges_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_mfa_challenges")),
        schema="identity",
    )


def downgrade() -> None:
    op.drop_table("mfa_challenges", schema="identity")
    op.drop_index(op.f("ix_recovery_codes_user_id"), table_name="recovery_codes", schema="identity")
    op.drop_table("recovery_codes", schema="identity")
    op.drop_table("totp_factors", schema="identity")
