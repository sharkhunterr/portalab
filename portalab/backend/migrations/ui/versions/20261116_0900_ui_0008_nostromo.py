"""ui universe themes, fifth wave — Nostromo (a ship's onboard computer: phosphor and amber on black, a
console docked at the bottom with the ship's clock and a heartbeat, MU/TH/UR's transmissions) (027)

Revision ID: ui_0008
Revises: ui_0007
Create Date: 2026-11-16 09:00:00
"""

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "ui_0008"
down_revision: str | Sequence[str] | None = "ui_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BUILTIN = Path(__file__).resolve().parents[3] / "src" / "portalab" / "modules" / "ui" / "themes" / "builtin"
KEYS = ("nostromo",)


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    for key in KEYS:
        definition = json.loads((BUILTIN / f"{key}.json").read_text(encoding="utf-8"))
        exists = bind.execute(sa.text("SELECT 1 FROM ui.themes WHERE key = :k"), {"k": key}).scalar()
        if exists:
            continue
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
    bind = op.get_bind()
    for key in KEYS:
        bind.execute(sa.text("DELETE FROM ui.themes WHERE key = :k"), {"k": key})
