"""support — feedback requests and replies (027): a form may be *requested* from members between two
dates (with a description), and staff may reply to a feedback

Revision ID: support_0003
Revises: support_0002
Create Date: 2026-10-12 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "support_0003"
down_revision: str | Sequence[str] | None = "support_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feedback_forms",
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        schema="support",
    )
    op.add_column("feedback_forms", sa.Column("icon", sa.String(40)), schema="support")
    op.add_column(
        "feedback_forms",
        sa.Column("requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="support",
    )
    op.add_column("feedback_forms", sa.Column("opens_at", sa.DateTime(timezone=True)), schema="support")
    op.add_column("feedback_forms", sa.Column("closes_at", sa.DateTime(timezone=True)), schema="support")
    op.add_column("feedback_items", sa.Column("reply", sa.Text()), schema="support")
    op.add_column("feedback_items", sa.Column("replied_at", sa.DateTime(timezone=True)), schema="support")
    op.create_index(
        "ix_feedback_items_form_submitter", "feedback_items", ["form_key", "submitter_id"], schema="support"
    )


def downgrade() -> None:
    op.drop_index("ix_feedback_items_form_submitter", "feedback_items", schema="support")
    for column in ("replied_at", "reply"):
        op.drop_column("feedback_items", column, schema="support")
    for column in ("closes_at", "opens_at", "requested", "icon", "description"):
        op.drop_column("feedback_forms", column, schema="support")
