"""ui site identity, issue 159 — the site's name, slogan, logo, icon and currency

Revision ID: ui_0017
Revises: ui_0016
Create Date: 2026-12-20 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ui_0017"
down_revision: str | Sequence[str] | None = "ui_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_identity",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("name", sa.String(40)),
        sa.Column("short_name", sa.String(12)),
        sa.Column("tagline", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("currency", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("currency_short", sa.String(8)),
        sa.Column("currency_icon", sa.String(32)),
        sa.Column("logo", sa.LargeBinary()),
        sa.Column("logo_type", sa.String(32)),
        sa.Column("icon", sa.LargeBinary()),
        sa.Column("icon_type", sa.String(32)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_site_identity_single"),
        schema="ui",
    )


def downgrade() -> None:
    op.drop_table("site_identity", schema="ui")
