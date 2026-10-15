"""gamification schema — more leaderboard periods (#128)

``leaderboard_snapshots.period`` also takes ``6months``, ``year`` and ``3years`` (the last six months, this
year, the last three years) beside ``all``, ``month`` and ``week``.

Revision ID: gamification_0008
Revises: gamification_0007
Create Date: 2026-10-15 09:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "gamification_0008"
down_revision: str | Sequence[str] | None = "gamification_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "ck_leaderboard_snapshots_period"


def upgrade() -> None:
    op.drop_constraint(op.f(NAME), "leaderboard_snapshots", schema="gamification", type_="check")
    op.create_check_constraint(
        op.f(NAME),
        "leaderboard_snapshots",
        "period IN ('all', 'month', 'week', '6months', 'year', '3years')",
        schema="gamification",
    )


def downgrade() -> None:
    op.execute("DELETE FROM gamification.leaderboard_snapshots WHERE period IN ('6months', 'year', '3years')")
    op.drop_constraint(op.f(NAME), "leaderboard_snapshots", schema="gamification", type_="check")
    op.create_check_constraint(
        op.f(NAME), "leaderboard_snapshots", "period IN ('all', 'month', 'week')", schema="gamification"
    )
