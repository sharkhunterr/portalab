"""news — what a scheduled edition tells (#323)

``news.newsletter_schedules.contents``: the contents switched on (none: the template's own sections).

Revision ID: news_0007
Revises: news_0006
Create Date: 2026-11-01 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "news_0007"
down_revision: str | Sequence[str] | None = "news_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("newsletter_schedules", sa.Column("contents", postgresql.JSONB()), schema="news")


def downgrade() -> None:
    op.drop_column("newsletter_schedules", "contents", schema="news")
