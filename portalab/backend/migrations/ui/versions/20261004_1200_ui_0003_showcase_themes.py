"""ui showcase themes — Orbit (orbit navigation, footer header) and Studio (top bar, flat) (spec 027 T060)

They show themes changing the arrangement principle, not only colors.

Revision ID: ui_0003
Revises: ui_0002
Create Date: 2026-10-04 12:00:00
"""

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from portalab.capabilities.visuals import interface_document

revision: str = "ui_0003"
down_revision: str | Sequence[str] | None = "ui_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 028: the interfaces' definitions are their packs' (``packs/builtin``), read where the release ships them
KEYS = ("orbit", "studio")


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    for key in KEYS:
        exists = bind.execute(sa.text("SELECT 1 FROM ui.themes WHERE key = :k"), {"k": key}).scalar()
        if exists:
            continue
        definition = interface_document(key)
        bind.execute(
            sa.text(
                "INSERT INTO ui.themes (id, key, name, source, owner, definition, schema_version, version, "
                "enabled, floor_report, created_at, updated_at) VALUES (:id, :key, :name, 'builtin', 'core', "
                "CAST(:definition AS jsonb), :schema_version, 1, true, CAST(:report AS jsonb), :now, :now)"
            ),
            {
                "id": uuid.uuid4(),
                "key": key,
                "name": definition["name"],
                "definition": json.dumps(definition),
                "schema_version": definition["schemaVersion"],
                "report": json.dumps({"ok": True, "checks": [], "violations": [], "seeded": True}),
                "now": now,
            },
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM ui.themes WHERE key IN ('orbit', 'studio')"))
