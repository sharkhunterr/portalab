"""media — the plays older than the catch-up's former window are looked at (#341)

The history catch-up now reaches back to each account's link (at most 30 days) instead of the last 48 hours.
The plays it never looked at, older than those 48 hours, were never meant to count (the progression the
portal lived began without them): they are marked looked at, so the change only applies from now on.

Revision ID: media_0022
Revises: media_0021
Create Date: 2026-11-02 20:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "media_0022"
down_revision: str | Sequence[str] | None = "media_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE media.activity SET rewarded_at = now() "
        "WHERE rewarded_at IS NULL AND started_at < now() - interval '48 hours'"
    )


def downgrade() -> None:
    pass  # looked at stays looked at
