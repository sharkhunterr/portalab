"""media — what each member says of a work: like, not for me, seen, later (#190)

``media.taste``: one verdict per member and work, beside what they watched and read, for their taste and the
recommendations made from it.

Revision ID: media_0016
Revises: media_0015
Create Date: 2026-10-28 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0016"
down_revision: str | Sequence[str] | None = "media_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "taste",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("verdict", sa.String(length=8), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("verdict IN ('like', 'dislike', 'seen', 'later')", name="ck_taste_verdict"),
        sa.ForeignKeyConstraint(
            ["object_id"], ["media.objects.id"], name="fk_taste_object_id_objects", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_taste_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "object_id", name="pk_taste"),
        schema="media",
    )
    op.create_index("ix_taste_user", "taste", ["user_id", "verdict", "updated_at"], schema="media")


def downgrade() -> None:
    op.drop_index("ix_taste_user", table_name="taste", schema="media")
    op.drop_table("taste", schema="media")
