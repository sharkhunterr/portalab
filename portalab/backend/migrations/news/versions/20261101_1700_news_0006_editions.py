"""news — self-writing newsletter editions and their templates (#316)

``news.newsletter_schedules``: the kind ``edition``, its template and notice;
``news.newsletter_templates``: the news desk's own templates (look and sections);
``news.newsletter_editions``: each edition — its snapshot, its e-mail, its status.

Revision ID: news_0006
Revises: news_0005
Create Date: 2026-11-01 17:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "news_0006"
down_revision: str | Sequence[str] | None = "news_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KIND = "ck_newsletter_schedules_kind"


def upgrade() -> None:
    op.drop_constraint(KIND, "newsletter_schedules", schema="news", type_="check")
    op.create_check_constraint(
        KIND,
        "newsletter_schedules",
        "kind IN ('releases', 'additions', 'upcoming', 'edition')",
        schema="news",
    )
    op.add_column("newsletter_schedules", sa.Column("template_key", sa.String(64)), schema="news")
    op.add_column("newsletter_schedules", sa.Column("notice", sa.Text()), schema="news")
    op.create_table(
        "newsletter_templates",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_newsletter_templates"),
        schema="news",
    )
    op.create_table(
        "newsletter_editions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid()),
        sa.Column("category_id", sa.Uuid()),
        sa.Column("template_key", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("emailed_at", sa.DateTime(timezone=True)),
        sa.Column("recipients", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "status IN ('preview', 'draft', 'published')", name="ck_newsletter_editions_status"
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["news.newsletter_schedules.id"],
            name="fk_newsletter_editions_schedule_id_newsletter_schedules",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["news.categories.id"],
            name="fk_newsletter_editions_category_id_categories",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_newsletter_editions"),
        sa.UniqueConstraint("token", name="uq_newsletter_editions_token"),
        schema="news",
    )
    op.create_index(
        "ix_newsletter_editions_published", "newsletter_editions", ["status", "published_at"], schema="news"
    )


def downgrade() -> None:
    op.drop_index("ix_newsletter_editions_published", "newsletter_editions", schema="news")
    op.drop_table("newsletter_editions", schema="news")
    op.drop_table("newsletter_templates", schema="news")
    op.drop_column("newsletter_schedules", "notice", schema="news")
    op.drop_column("newsletter_schedules", "template_key", schema="news")
    op.drop_constraint(KIND, "newsletter_schedules", schema="news", type_="check")
    op.create_check_constraint(
        KIND, "newsletter_schedules", "kind IN ('releases', 'additions', 'upcoming')", schema="news"
    )
