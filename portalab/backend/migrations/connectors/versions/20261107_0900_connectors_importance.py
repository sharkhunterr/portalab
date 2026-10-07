"""connectors schema — how much a service matters and when its outage becomes an incident (027)

Revision ID: connectors_0004
Revises: connectors_0003
Create Date: 2026-11-07 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "connectors_0004"
down_revision: str | Sequence[str] | None = "connectors_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column("importance", sa.String(length=10), nullable=False, server_default="major"),
        schema="connectors",
    )
    op.create_check_constraint(
        op.f("ck_services_importance"),
        "services",
        "importance IN ('critical', 'major', 'minor', 'internal')",
        schema="connectors",
    )
    # minutes of outage before an incident is declared; NULL: the importance's default, 0: never
    op.add_column(
        "services", sa.Column("incident_after_minutes", sa.Integer(), nullable=True), schema="connectors"
    )
    op.add_column(
        "services",
        sa.Column("incident_auto_resolve", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="connectors",
    )


def downgrade() -> None:
    op.drop_column("services", "incident_auto_resolve", schema="connectors")
    op.drop_column("services", "incident_after_minutes", schema="connectors")
    op.drop_constraint(op.f("ck_services_importance"), "services", schema="connectors")
    op.drop_column("services", "importance", schema="connectors")
