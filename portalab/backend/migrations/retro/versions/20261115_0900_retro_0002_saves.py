"""retro schema — the members' saves and save states (issue 420).

Revision ID: retro_0002
Revises: retro_0001
Create Date: 2026-11-15 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "retro_0002"
down_revision: str | Sequence[str] | None = "retro_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "saves",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("core", sa.String(64), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("screenshot", sa.LargeBinary(), nullable=True),
        sa.Column("updated_at", TZ, nullable=False),
        sa.Column("remote_id", sa.String(64), nullable=True),
        sa.Column("synced_at", TZ, nullable=True),
        sa.CheckConstraint("kind IN ('sram', 'state')", name=op.f("ck_saves_kind")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name=op.f("fk_saves_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saves")),
        sa.UniqueConstraint("user_id", "service_id", "external_id", "kind", "slot", name="uq_saves_slot"),
        schema="retro",
    )
    op.create_index("ix_saves_user_object", "saves", ["user_id", "object_id"], schema="retro")
    op.create_index(
        "ix_saves_unsynced",
        "saves",
        ["updated_at"],
        schema="retro",
        postgresql_where=sa.text("synced_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("saves", schema="retro")
