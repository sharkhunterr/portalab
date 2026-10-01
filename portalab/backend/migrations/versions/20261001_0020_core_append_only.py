"""core.reject_append_only_mutation() — trigger function shared by every append-only table

Revision ID: core_0003
Revises: core_0002
Create Date: 2026-10-01 00:20:00
"""

from collections.abc import Sequence

from alembic import op

from portalab.core.append_only import FUNCTION, FUNCTION_DDL

revision: str = "core_0003"
down_revision: str | Sequence[str] | None = "core_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(FUNCTION_DDL)


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION}()")
