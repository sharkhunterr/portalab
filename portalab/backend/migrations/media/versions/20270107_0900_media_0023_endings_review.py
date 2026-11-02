"""media — the plays judged abandoned are looked at again with the end credits' new leeway (#342)

A play stopped in the last two minutes before its end credits is now finished (it was 30 s). The job
``media.endings_review`` is queued once: it looks at the films and episodes judged abandoned since the
progression began (its first grant, at most 30 days back) and publishes the finish of those that reach their
end now — it asks the media servers where the credits begin, so it runs in the worker.

Revision ID: media_0023
Revises: media_0022
Create Date: 2026-11-02 21:00:00
"""

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0023"
down_revision: str | Sequence[str] | None = "media_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT to_regclass('gamification.transactions')")) is None:
        return  # a fresh portal: nothing was judged yet
    first = bind.scalar(sa.text("SELECT min(recorded_at) FROM gamification.transactions"))
    if first is None:
        return  # no grant yet: nothing to look at again
    since = bind.scalar(sa.text("SELECT greatest(now() - interval '30 days', :first)"), {"first": first})
    bind.execute(
        sa.text(
            "INSERT INTO core.job (id, queue, kind, payload, dedup_key, status, run_at, attempts, max_attempts,"
            " created_at, updated_at) VALUES (:id, 'default', 'media.endings_review', CAST(:payload AS jsonb),"
            " 'media.endings_review:342', 'queued', now(), 0, 3, now(), now()) ON CONFLICT DO NOTHING"
        ),
        {"id": uuid.uuid4(), "payload": json.dumps({"since": since.isoformat()})},
    )


def downgrade() -> None:
    pass  # a finish published stays published
