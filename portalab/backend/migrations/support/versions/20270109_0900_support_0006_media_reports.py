"""support — a problem with a media reported from its page: the ticket type that takes them, the media of a ticket

Revision ID: support_0006
Revises: support_0005
Create Date: 2027-01-09 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "support_0006"
down_revision: str | Sequence[str] | None = "support_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # #354: the administrator's type « problem with a media » (one at most), and the media a ticket is about
    op.add_column(
        "ticket_types",
        sa.Column("media", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="support",
    )
    op.add_column("tickets", sa.Column("media_id", sa.Uuid()), schema="support")
    op.create_index("ix_tickets_media", "tickets", ["media_id"], schema="support")


def downgrade() -> None:
    op.drop_index("ix_tickets_media", table_name="tickets", schema="support")
    op.drop_column("tickets", "media_id", schema="support")
    op.drop_column("ticket_types", "media", schema="support")
