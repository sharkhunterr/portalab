"""media — the CNC's film visas (#478)

The French cinema regulator's open list of exploitation visas (data.gouv.fr: visa number, title, year,
direction, decision — « Tout public », « Avertissement », « Interdit -12 ans »…), kept to tell a film's
French classification in full: the warning that comes with « tous publics », the date of the decision's
country. Refreshed every week from the open data.

Revision ID: media_0030
Revises: media_0029
Create Date: 2026-11-16 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0030"
down_revision: str | Sequence[str] | None = "media_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cnc_visas",
        sa.Column("visa", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(400), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(300), nullable=True),
        sa.Column("decision", sa.String(80), nullable=False),
        sa.PrimaryKeyConstraint("visa", name="pk_cnc_visas"),
        schema="media",
    )
    op.create_index("ix_cnc_visas_key_year", "cnc_visas", ["key", "year"], schema="media")


def downgrade() -> None:
    op.drop_index("ix_cnc_visas_key_year", table_name="cnc_visas", schema="media")
    op.drop_table("cnc_visas", schema="media")
