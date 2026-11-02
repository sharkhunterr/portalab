"""news — where an automatic newsletter goes: the portal's news, e-mail, or both (#332)

``news.newsletter_schedules.publish``: whether its letters are published in the portal (in « Letters », and an
article in its channel's news); ``news.newsletter_editions.status`` gains ``sent``: a letter e-mailed only, not
published in the portal.

Revision ID: news_0010
Revises: news_0009
Create Date: 2026-11-02 08:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "news_0010"
down_revision: str | Sequence[str] | None = "news_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "newsletter_schedules",
        sa.Column("publish", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="news",
    )
    op.drop_constraint("ck_newsletter_editions_status", "newsletter_editions", schema="news")
    op.create_check_constraint(
        "ck_newsletter_editions_status",
        "newsletter_editions",
        "status IN ('preview', 'draft', 'published', 'sent')",
        schema="news",
    )


def downgrade() -> None:
    op.execute("UPDATE news.newsletter_editions SET status = 'draft' WHERE status = 'sent'")
    op.drop_constraint("ck_newsletter_editions_status", "newsletter_editions", schema="news")
    op.create_check_constraint(
        "ck_newsletter_editions_status",
        "newsletter_editions",
        "status IN ('preview', 'draft', 'published')",
        schema="news",
    )
    op.drop_column("newsletter_schedules", "publish", schema="news")
