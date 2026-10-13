"""media — book positions: listening and reading in the portal (#20, #21)

``media.book_positions``: where a member stopped in a book, per format (``audio``, ``epub``, ``pdf``,
``cbx``) — seconds, an EPUB CFI or a page — and when the last progress event was published.

Revision ID: media_0007
Revises: media_0006
Create Date: 2026-12-08 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0007"
down_revision: str | Sequence[str] | None = "media_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "book_positions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("format", sa.String(length=8), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("file_ref", sa.String(length=80), nullable=True),
        sa.Column("position", sa.String(length=2000), nullable=False),
        sa.Column("track", sa.Integer(), nullable=True),
        sa.Column("percent", sa.Float(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.Column("event_at", TZ, nullable=True),
        sa.ForeignKeyConstraint(
            ["object_id"], ["media.objects.id"], name="fk_book_positions_object_id_objects"
        ),
        sa.PrimaryKeyConstraint("user_id", "object_id", "format", name="pk_book_positions"),
        schema="media",
    )
    op.create_index("ix_book_positions_user", "book_positions", ["user_id", "updated_at"], schema="media")


def downgrade() -> None:
    op.drop_index("ix_book_positions_user", table_name="book_positions", schema="media")
    op.drop_table("book_positions", schema="media")
