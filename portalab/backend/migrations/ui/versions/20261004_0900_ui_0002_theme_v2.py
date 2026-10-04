"""ui theme v2 — seed the ``portalab`` theme family (dark default, light variant) (spec 027 T010)

Built-in v1 documents stay as stored: v1 is upgraded on read (the v2 blocks are optional). The default
theme itself is a setting default (``ui.defaultTheme`` = ``portalab``), so an explicitly configured value
is kept.

Revision ID: ui_0002
Revises: ui_0001
Create Date: 2026-10-04 09:00:00
"""

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "ui_0002"
down_revision: str | Sequence[str] | None = "ui_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BUILTIN = Path(__file__).resolve().parents[3] / "src" / "portalab" / "modules" / "ui" / "themes" / "builtin"
KEYS = ("portalab-dark", "portalab-light")


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    for key in KEYS:
        exists = bind.execute(sa.text("SELECT 1 FROM ui.themes WHERE key = :k"), {"k": key}).scalar()
        if exists:
            continue
        definition = json.loads((BUILTIN / f"{key}.json").read_text(encoding="utf-8"))
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
    op.execute(sa.text("DELETE FROM ui.themes WHERE key IN ('portalab-dark', 'portalab-light')"))
