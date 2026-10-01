"""core baseline — kernel schema

Revision ID: core_0001
Revises:
Create Date: 2026-10-01 00:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "core_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("core",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "core"')


def downgrade() -> None:
    # Development only. The schema also hosts the Alembic version table, so it is kept.
    pass
