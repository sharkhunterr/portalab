"""identity schema — the guided tour is an onboarding step (027)

Revision ID: identity_0003
Revises: identity_0002
Create Date: 2026-10-10 10:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "identity_0003"
down_revision: str | Sequence[str] | None = "identity_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STEPS = ("profile", "interests", "notifications", "privacy", "dashboard", "discovery")


def _check(steps: tuple[str, ...]) -> None:
    op.drop_constraint("ck_onboarding_progress_step", "onboarding_progress", schema="identity", type_="check")
    op.create_check_constraint(
        "ck_onboarding_progress_step",
        "onboarding_progress",
        "step IN (" + ", ".join(f"'{s}'" for s in steps) + ")",
        schema="identity",
    )


def upgrade() -> None:
    _check((*STEPS, "tour"))


def downgrade() -> None:
    op.execute("DELETE FROM identity.onboarding_progress WHERE step = 'tour'")
    _check(STEPS)
