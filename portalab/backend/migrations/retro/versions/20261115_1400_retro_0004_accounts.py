"""retro schema — the members' own accounts in the game libraries (issue 426).

Revision ID: retro_0004
Revises: retro_0003
Create Date: 2026-11-15 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "retro_0004"
down_revision: str | Sequence[str] | None = "retro_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(8), nullable=False),
        sa.Column("token", sa.String(2048), nullable=True),
        sa.Column("device_code", sa.String(1024), nullable=True),
        sa.Column("user_code", sa.String(32), nullable=True),
        sa.Column("path", sa.String(512), nullable=True),
        sa.Column("pending_until", TZ, nullable=True),
        sa.Column("interval", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(64), nullable=True),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", TZ, nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("state IN ('pending', 'linked', 'expired')", name=op.f("ck_accounts_state")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name=op.f("fk_accounts_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "service_id", name=op.f("pk_accounts")),
        schema="retro",
    )
    op.add_column("saves", sa.Column("remote_account", sa.String(64), nullable=True), schema="retro")


def downgrade() -> None:
    op.drop_column("saves", "remote_account", schema="retro")
    op.drop_table("accounts", schema="retro")
