"""media — members' reviews of what they watched, read, listened to or played: a rating, a few words (#355)

``media.reviews``: one review per member and work — a rating from 1 to 5 (required), a comment (optional).

Revision ID: media_0025
Revises: media_0024
Create Date: 2027-01-09 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0025"
down_revision: str | Sequence[str] | None = "media_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
        sa.ForeignKeyConstraint(
            ["object_id"], ["media.objects.id"], name="fk_reviews_object_id_objects", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_reviews_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "object_id", name="pk_reviews"),
        schema="media",
    )
    op.create_index("ix_reviews_object", "reviews", ["object_id", "updated_at"], schema="media")


def downgrade() -> None:
    op.drop_index("ix_reviews_object", table_name="reviews", schema="media")
    op.drop_table("reviews", schema="media")
