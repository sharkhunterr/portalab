"""retro schema — the sittings of the games played in the portal (issue 419).

Revision ID: retro_0001
Revises:
Create Date: 2026-11-14 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "retro_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("retro",)
depends_on: str | Sequence[str] | None = ("identity_0006",)

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "retro"')
    op.create_table(
        "sittings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("platform_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("core", sa.String(64), nullable=False),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("last_seen_at", TZ, nullable=False),
        sa.Column("ended_at", TZ, nullable=True),
        sa.Column("played_s", sa.Float(), nullable=False),
        sa.Column("told_at", TZ, nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name=op.f("fk_sittings_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sittings")),
        schema="retro",
    )
    op.create_index("ix_sittings_user_id", "sittings", ["user_id", "started_at"], schema="retro")
    op.create_index(
        "ix_sittings_open",
        "sittings",
        ["last_seen_at"],
        schema="retro",
        postgresql_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("sittings", schema="retro")
    op.execute('DROP SCHEMA IF EXISTS "retro"')
