"""gamification — the daily quest « Mailbox » (read a notification) is retired: too invasive (issue 442)

Revision ID: gamification_0014
Revises: gamification_0013
Create Date: 2026-11-15 12:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "gamification_0014"
down_revision: str | Sequence[str] | None = "gamification_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE gamification.quests SET status = 'retired' WHERE key = 'daily_inbox' AND status = 'active'"
    )


def downgrade() -> None:
    pass  # an administrator brings a quest back from the Gamification page
