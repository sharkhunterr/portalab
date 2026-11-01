"""news — the statistics' charts of a scheduled edition (#324)

``news.newsletter_schedules.charts``: the charts switched on (none: the usual ones).

Revision ID: news_0008
Revises: news_0007
Create Date: 2026-11-01 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "news_0008"
down_revision: str | Sequence[str] | None = "news_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("newsletter_schedules", sa.Column("charts", postgresql.JSONB()), schema="news")


def downgrade() -> None:
    op.drop_column("newsletter_schedules", "charts", schema="news")
