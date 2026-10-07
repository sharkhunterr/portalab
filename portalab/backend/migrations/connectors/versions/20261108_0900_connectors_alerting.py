"""connectors schema — a service's own alerting overrides over its importance's rules (027)

The two columns of ``connectors_0004`` (incident delay, auto-close) become fields of one ``alerting`` object
that may override any rule of the importance (incident, delays, notifications, e-mails, portal health).

Revision ID: connectors_0005
Revises: connectors_0004
Create Date: 2026-11-08 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "connectors_0005"
down_revision: str | Sequence[str] | None = "connectors_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column("alerting", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="connectors",
    )
    op.execute(
        """
        UPDATE connectors.services SET alerting =
            CASE
                WHEN incident_after_minutes = 0 THEN jsonb_build_object('incident', false)
                WHEN incident_after_minutes IS NOT NULL
                    THEN jsonb_build_object('incident', true, 'incident_after', incident_after_minutes)
                ELSE '{}'::jsonb
            END
            || CASE WHEN incident_auto_resolve THEN '{}'::jsonb
                    ELSE jsonb_build_object('auto_resolve', false) END
        """
    )
    op.drop_column("services", "incident_auto_resolve", schema="connectors")
    op.drop_column("services", "incident_after_minutes", schema="connectors")


def downgrade() -> None:
    op.add_column(
        "services", sa.Column("incident_after_minutes", sa.Integer(), nullable=True), schema="connectors"
    )
    op.add_column(
        "services",
        sa.Column("incident_auto_resolve", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="connectors",
    )
    op.execute(
        """
        UPDATE connectors.services SET
            incident_after_minutes = CASE
                WHEN alerting->>'incident' = 'false' THEN 0
                ELSE (alerting->>'incident_after')::int END,
            incident_auto_resolve = COALESCE((alerting->>'auto_resolve')::boolean, true)
        """
    )
    op.drop_column("services", "alerting", schema="connectors")
