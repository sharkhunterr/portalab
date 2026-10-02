"""shell initial schema — contribution diagnostics and navigation epochs (spec 004 T007)

Revision ID: shell_0001
Revises:
Create Date: 2026-10-03 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "shell_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("shell",)
depends_on: str | Sequence[str] | None = ("core_0005",)

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "shell"')
    op.create_table(
        "contribution_errors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner", sa.String(128), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("detail", sa.String(512), nullable=False),
        sa.Column("first_seen_at", TZ, nullable=False),
        sa.Column("last_seen_at", TZ, nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_contribution_errors"),
        sa.UniqueConstraint("owner", "key", "reason", name="uq_contribution_errors"),
        sa.CheckConstraint(
            "reason IN ('schema', 'duplicate', 'conflict', 'runtime')", name="ck_contribution_errors_reason"
        ),
        schema="shell",
    )
    op.create_table(
        "epochs",
        sa.Column("name", sa.String(32), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("name", name="pk_epochs"),
        schema="shell",
    )
    op.execute(
        "INSERT INTO shell.epochs (name, value, updated_at) VALUES ('permission', 0, now()), ('module', 0, now())"
    )


def downgrade() -> None:
    op.drop_table("epochs", schema="shell")
    op.drop_table("contribution_errors", schema="shell")
    op.execute('DROP SCHEMA IF EXISTS "shell"')
