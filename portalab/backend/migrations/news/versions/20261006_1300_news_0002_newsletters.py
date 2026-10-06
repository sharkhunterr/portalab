"""news — channels and newsletters (027)

Categories become channels (description, icon, ``newsletter``: e-mailed to subscribers); an article may be
e-mailed when published (``email_on_publish``, once: ``emailed_at``); automatic newsletters are scheduled
(``newsletter_schedules``).

Revision ID: news_0002
Revises: news_0001
Create Date: 2026-10-06 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "news_0002"
down_revision: str | Sequence[str] | None = "news_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("description", sa.String(length=300), nullable=False, server_default=""),
        schema="news",
    )
    op.add_column("categories", sa.Column("icon", sa.String(length=40), nullable=True), schema="news")
    op.add_column(
        "categories",
        sa.Column("newsletter", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="news",
    )
    op.add_column(
        "articles",
        sa.Column("email_on_publish", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="news",
    )
    op.add_column(
        "articles", sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True), schema="news"
    )
    op.create_table(
        "newsletter_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("media_kinds", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("cadence", sa.String(length=10), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hour", sa.Integer(), nullable=False, server_default="9"),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="fr"),
        sa.Column("email", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_article_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('releases', 'additions', 'upcoming')", name="ck_newsletter_schedules_kind"
        ),
        sa.CheckConstraint(
            "cadence IN ('daily', 'weekly', 'monthly')", name="ck_newsletter_schedules_cadence"
        ),
        sa.CheckConstraint(
            "weekday BETWEEN 0 AND 6 AND hour BETWEEN 0 AND 23", name="ck_newsletter_schedules_when"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["news.categories.id"], name="fk_newsletter_schedules_category_id_categories"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_newsletter_schedules"),
        schema="news",
    )


def downgrade() -> None:
    op.drop_table("newsletter_schedules", schema="news")
    op.drop_column("articles", "emailed_at", schema="news")
    op.drop_column("articles", "email_on_publish", schema="news")
    op.drop_column("categories", "newsletter", schema="news")
    op.drop_column("categories", "icon", schema="news")
    op.drop_column("categories", "description", schema="news")
