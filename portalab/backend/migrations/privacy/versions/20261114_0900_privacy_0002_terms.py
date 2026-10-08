"""privacy — terms of use (027)

``terms_versions`` (append-only published history) and ``terms_acceptances`` (which version each member
accepted), ``terms_settings`` (whether they are asked at all — optional).

Revision ID: privacy_0002
Revises: privacy_0001
Create Date: 2026-11-14 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from portalab.core.append_only import append_only_ddl, drop_append_only_ddl

revision: str = "privacy_0002"
down_revision: str | Sequence[str] | None = "privacy_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "terms_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False, server_default=""),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("requires_acceptance", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("published_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_terms_versions"),
        sa.UniqueConstraint("version", name="uq_terms_versions_version"),
        schema="privacy",
    )
    for statement in append_only_ddl("privacy", "terms_versions"):
        op.execute(statement)
    op.create_table(
        "terms_acceptances",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("accepted_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("user_id", "version", name="pk_terms_acceptances"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_terms_acceptances_user", ondelete="CASCADE"
        ),
        schema="privacy",
    )
    op.create_table(
        "terms_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_terms_settings"),
        sa.CheckConstraint("id = 1", name="ck_terms_settings_single"),
        schema="privacy",
    )


def downgrade() -> None:
    op.drop_table("terms_settings", schema="privacy")
    op.drop_table("terms_acceptances", schema="privacy")
    for statement in drop_append_only_ddl("privacy", "terms_versions"):
        op.execute(statement)
    op.drop_table("terms_versions", schema="privacy")
