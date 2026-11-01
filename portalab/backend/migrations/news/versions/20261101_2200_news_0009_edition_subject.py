"""news — an automatic newsletter's e-mail subject and period (#325)

``news.newsletter_schedules.subject``: the e-mail's subject, with its variables (none: the usual one);
``news.newsletter_schedules.days``: the days each edition tells (none: its cadence's).

Revision ID: news_0009
Revises: news_0008
Create Date: 2026-11-01 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "news_0009"
down_revision: str | Sequence[str] | None = "news_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("newsletter_schedules", sa.Column("subject", sa.String(200)), schema="news")
    op.add_column("newsletter_schedules", sa.Column("days", sa.Integer()), schema="news")


def downgrade() -> None:
    op.drop_column("newsletter_schedules", "days", schema="news")
    op.drop_column("newsletter_schedules", "subject", schema="news")
