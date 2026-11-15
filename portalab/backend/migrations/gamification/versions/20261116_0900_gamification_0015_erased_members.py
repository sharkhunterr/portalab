"""gamification — the accounts erased (issue 450): their ledger rows stay (append-only, non-identifying) but the
administration's screens leave them out; those erased before are listed from the identity's tombstones

Revision ID: gamification_0015
Revises: gamification_0014
Create Date: 2026-11-16 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "gamification_0015"
down_revision: str | Sequence[str] | None = "gamification_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "erased_members",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("erased_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_erased_members")),
        schema="gamification",
    )
    op.execute(
        "INSERT INTO gamification.erased_members (user_id, erased_at) "
        "SELECT u.id, now() FROM identity.users u WHERE u.state = 'deleted' "
        "AND EXISTS (SELECT 1 FROM gamification.transactions t WHERE t.user_id = u.id)"
    )


def downgrade() -> None:
    op.drop_table("erased_members", schema="gamification")
