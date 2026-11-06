"""requests schema — the team as a request service (#378): each request asked of the team becomes the
portal's own request (media.requests, under the team's service), as a film's is; its « me too » and its
own requester, price and decision go (the portal's request keeps who asked and the decision)

Revision ID: requests_0002
Revises: requests_0001
Create Date: 2026-11-06 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "requests_0002"
down_revision: str | Sequence[str] | None = "requests_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = ("media_0025",)

# the team's service: uuid5(UUID(int=0), "portalab:requests:team") — written in the statement below


def upgrade() -> None:
    # every request asked of the team, the portal's own — who asked, where it stands, what was told of it
    op.execute(
        """
        INSERT INTO media.requests (
            id, object_id, external_ref, requester_user_id, service_id, external_request_id, state,
            source_state, idempotency_key, counted, requested_at, updated_at
        )
        SELECT
            r.id,
            CASE WHEN r.status = 'available' THEN r.object_id END,
            jsonb_strip_nulls(jsonb_build_object(
                'ids', (SELECT coalesce(jsonb_object_agg(key, value ->> 0), '{}') FROM jsonb_each(r.ids)),
                'kind', r.kind,
                'title', r.title,
                'creators', CASE WHEN jsonb_array_length(r.creators) > 0 THEN r.creators END,
                'year', r.year,
                'details', CASE WHEN r.details <> '{}'::jsonb THEN r.details END,
                'note', r.note,
                'decision', CASE WHEN r.status = 'refused' THEN jsonb_build_object(
                    'approved', false, 'reason', r.reason, 'by', r.decided_by::text, 'at', r.updated_at
                ) END
            )),
            r.requester_id,
            '71ab2125-cb76-5dcb-a322-778b0eb93b90'::uuid,  -- the team's service
            r.id::text,
            CASE r.status
                WHEN 'new' THEN 'pending'
                WHEN 'accepted' THEN 'approved'
                WHEN 'in_progress' THEN 'processing'
                WHEN 'available' THEN 'available'
                WHEN 'refused' THEN 'declined'
                ELSE 'cancelled'
            END,
            r.status,
            NULL,
            'none',
            r.created_at,
            r.updated_at
        FROM requests.requests r
        ON CONFLICT DO NOTHING
        """
    )
    op.drop_table("supporters", schema="requests")
    for column in ("requester_id", "spend_id", "decided_by", "reason"):
        op.drop_column("requests", column, schema="requests")


def downgrade() -> None:
    """Development only: the columns and the « me too » back (empty), the portal's requests kept."""
    op.add_column("requests", sa.Column("requester_id", sa.Uuid(), nullable=True), schema="requests")
    op.add_column("requests", sa.Column("spend_id", sa.Uuid(), nullable=True), schema="requests")
    op.add_column("requests", sa.Column("decided_by", sa.Uuid(), nullable=True), schema="requests")
    op.add_column("requests", sa.Column("reason", sa.String(500), nullable=True), schema="requests")
    op.create_table(
        "supporters",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("asked", sa.Boolean(), nullable=False),
        sa.Column("since", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("request_id", "user_id", name="pk_supporters"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["requests.requests.id"], name="fk_supporters_request_id", ondelete="CASCADE"
        ),
        schema="requests",
    )
