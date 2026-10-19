"""privacy — the terms of use on the sign-in page (issue 157)

``terms_settings.on_sign_in``: whether the sign-in page offers the terms to read — off by default, on every
existing instance too (the administrators turn it on in Communication, Terms of use).

Revision ID: privacy_0003
Revises: privacy_0002
Create Date: 2026-12-19 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "privacy_0003"
down_revision: str | Sequence[str] | None = "privacy_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "terms_settings",
        sa.Column("on_sign_in", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="privacy",
    )


def downgrade() -> None:
    op.drop_column("terms_settings", "on_sign_in", schema="privacy")
