"""notify — announcements (027): what the administrator announced, through which channels (notification,
e-mail, banner) and until when the banner shows

Revision ID: notify_0003
Revises: notify_0002
Create Date: 2026-10-12 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "notify_0003"
down_revision: str | Sequence[str] | None = "notify_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("link", sa.String(256)),
        sa.Column("tone", sa.String(10), nullable=False, server_default="info"),
        sa.Column("channels", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("banner", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("banner_until", sa.DateTime(timezone=True)),
        sa.Column("recipients", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "tone IN ('info', 'success', 'warning', 'critical')", name="ck_announcements_tone"
        ),
        schema="notify",
    )
    op.create_index("ix_announcements_banner", "announcements", ["banner", "banner_until"], schema="notify")


def downgrade() -> None:
    op.drop_index("ix_announcements_banner", "announcements", schema="notify")
    op.drop_table("announcements", schema="notify")
