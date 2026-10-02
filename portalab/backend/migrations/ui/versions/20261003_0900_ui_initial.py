"""ui initial schema — theme registry, seeded with the built-in themes (spec 022 T010)

Revision ID: ui_0001
Revises:
Create Date: 2026-10-03 09:00:00
"""

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ui_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("ui",)
depends_on: str | Sequence[str] | None = ("core_0005",)

TZ = sa.DateTime(timezone=True)
BUILTIN = Path(__file__).resolve().parents[3] / "src" / "portalab" / "modules" / "ui" / "themes" / "builtin"


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "ui"')
    themes = op.create_table(
        "themes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(48), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("owner", sa.String(128), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("floor_report", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_themes"),
        sa.UniqueConstraint("key", name="uq_themes_key"),
        schema="ui",
    )
    now = datetime.now(UTC)
    rows = []
    for key in ("light", "dark", "high-contrast"):
        definition = json.loads((BUILTIN / f"{key}.json").read_text(encoding="utf-8"))
        rows.append(
            {
                "id": uuid.uuid4(),
                "key": key,
                "name": definition["name"],
                "source": "builtin",
                "owner": "core",
                "definition": definition,
                "schema_version": definition["schemaVersion"],
                "version": 1,
                "enabled": True,
                "floor_report": {"ok": True, "checks": [], "violations": [], "seeded": True},
                "created_at": now,
                "updated_at": now,
            }
        )
    op.bulk_insert(themes, rows)


def downgrade() -> None:
    op.drop_table("themes", schema="ui")
    op.execute('DROP SCHEMA IF EXISTS "ui"')
