"""support — a ticket type's tickets shown to every member on the media they are about (#354)

Revision ID: support_0007
Revises: support_0006
Create Date: 2027-01-10 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "support_0007"
down_revision: str | Sequence[str] | None = "support_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # public: every member sees its open tickets on a media's page (no name, no description); else only theirs
    op.add_column(
        "ticket_types",
        sa.Column("public", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="support",
    )


def downgrade() -> None:
    op.drop_column("ticket_types", "public", schema="support")
