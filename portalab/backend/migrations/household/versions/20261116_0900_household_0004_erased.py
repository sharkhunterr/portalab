"""household — what deleted profiles left behind before their household took part in erasure (issue 450): their
household row, and the access requests they made (unnamed, they waited for their master)

Revision ID: household_0004
Revises: household_0003
Create Date: 2026-11-16 09:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "household_0004"
down_revision: str | Sequence[str] | None = "household_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM household.members m USING identity.users u "
        "WHERE m.user_id = u.id AND m.kind <> 'owner' AND u.state = 'deleted'"
    )
    op.execute(
        "DELETE FROM household.access_requests r "
        "WHERE NOT EXISTS (SELECT 1 FROM household.members m WHERE m.user_id = r.profile_id)"
    )


def downgrade() -> None:
    pass  # erased data does not come back
