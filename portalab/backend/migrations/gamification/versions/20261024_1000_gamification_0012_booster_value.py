"""gamification — the boosters a reward rule gives, in the ledger as a value of their own (issue 234)

Revision ID: gamification_0012
Revises: gamification_0011
Create Date: 2026-10-24 10:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "gamification_0012"
down_revision: str | Sequence[str] | None = "gamification_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("balances", "transactions", "withheld")


def upgrade() -> None:
    for table in TABLES:
        op.drop_constraint(f"ck_{table}_value", table, schema="gamification", type_="check")
        op.create_check_constraint(
            f"ck_{table}_value",
            table,
            "value IN ('xp', 'contribution', 'coins', 'booster')",
            schema="gamification",
        )


def downgrade() -> None:
    op.execute("DELETE FROM gamification.balances WHERE value = 'booster'")
    for table in TABLES:
        op.drop_constraint(f"ck_{table}_value", table, schema="gamification", type_="check")
        op.create_check_constraint(
            f"ck_{table}_value", table, "value IN ('xp', 'contribution', 'coins')", schema="gamification"
        )
