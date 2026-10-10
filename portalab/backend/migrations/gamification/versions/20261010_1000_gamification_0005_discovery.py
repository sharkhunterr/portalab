"""gamification schema — discovery missions: once-only quests of a new member's first steps (027)

Revision ID: gamification_0005
Revises: gamification_0004
Create Date: 2026-10-10 10:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "gamification_0005"
down_revision: str | Sequence[str] | None = "gamification_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _kinds(kinds: str) -> None:
    op.drop_constraint("ck_quests_kind", "quests", schema="gamification", type_="check")
    op.create_check_constraint("ck_quests_kind", "quests", f"kind IN ({kinds})", schema="gamification")


def upgrade() -> None:
    _kinds("'quest', 'daily', 'challenge', 'discovery'")


def downgrade() -> None:
    op.execute("UPDATE gamification.quests SET kind = 'quest' WHERE kind = 'discovery'")
    _kinds("'quest', 'daily', 'challenge'")
