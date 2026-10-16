"""visuals initial schema — the registry of visual packs (spec 028 T005)

Revision ID: visuals_0001
Revises:
Create Date: 2026-12-15 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "visuals_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("visuals",)
depends_on: str | Sequence[str] | None = ("core_0005",)

TZ = sa.DateTime(timezone=True)
JSON = postgresql.JSONB(astext_type=sa.Text())
S = "visuals"


def upgrade() -> None:
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{S}"')
    op.create_table(
        "packs",
        sa.Column("id", sa.String(48), nullable=False),
        sa.Column("builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("socle", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", JSON, nullable=False, server_default="{}"),
        sa.Column("state", sa.String(16), nullable=False, server_default="disabled"),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("remote", JSON, nullable=True),
        sa.Column("names", JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_packs"),
        sa.CheckConstraint("state IN ('enabled', 'disabled', 'archived', 'removed')", name="ck_packs_state"),
        sa.CheckConstraint("NOT socle OR state = 'enabled'", name="ck_packs_socle_enabled"),
        schema=S,
    )
    op.create_index(
        "uq_packs_socle", "packs", ["socle"], unique=True, schema=S, postgresql_where=sa.text("socle")
    )
    op.create_table(
        "pack_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pack_id", sa.String(48), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("folder", sa.String(200), nullable=False),
        sa.Column("step", sa.String(16), nullable=False, server_default="imported"),
        sa.Column("outcomes", JSON, nullable=False, server_default="{}"),
        sa.Column("report", JSON, nullable=False, server_default="{}"),
        sa.Column("measures", JSON, nullable=True),
        sa.Column("draft", JSON, nullable=True),
        sa.Column("decision", JSON, nullable=True),
        sa.Column("changes", JSON, nullable=True),
        sa.Column("ever_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("detected_at", TZ, nullable=False),
        sa.Column("published_at", TZ, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_pack_versions"),
        sa.ForeignKeyConstraint(["pack_id"], [f"{S}.packs.id"], name="fk_pack_versions_pack_id_packs"),
        sa.UniqueConstraint("pack_id", "version", name="uq_pack_versions_number"),
        sa.CheckConstraint(
            "step IN ('imported', 'analysed', 'tested', 'reviewed', 'published', 'refused', 'superseded', "
            "'purged')",
            name="ck_pack_versions_step",
        ),
        schema=S,
    )
    op.create_index("ix_pack_versions_pack_id", "pack_versions", ["pack_id"], schema=S)
    op.create_table(
        "elements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("folder", sa.String(200), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("look", sa.String(48), nullable=True),
        sa.Column("product_key", sa.String(64), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("data", JSON, nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("id", name="pk_elements"),
        sa.ForeignKeyConstraint(
            ["version_id"],
            [f"{S}.pack_versions.id"],
            name="fk_elements_version_id_pack_versions",
            ondelete="CASCADE",
        ),
        schema=S,
    )
    op.create_index("ix_elements_version_id", "elements", ["version_id"], schema=S)
    op.create_index("ix_elements_product_key", "elements", ["product_key"], schema=S)
    op.create_index("ix_elements_type_look", "elements", ["type", "look"], schema=S)
    op.create_table(
        "look_claims",
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("look", sa.String(48), nullable=False),
        sa.Column("pack_id", sa.String(48), nullable=False),
        sa.Column("element_id", sa.Uuid(), nullable=False),
        sa.Column("replaced_from", sa.String(48), nullable=True),
        sa.PrimaryKeyConstraint("type", "look", name="pk_look_claims"),
        sa.ForeignKeyConstraint(["pack_id"], [f"{S}.packs.id"], name="fk_look_claims_pack_id_packs"),
        schema=S,
    )
    op.create_index("ix_look_claims_pack_id", "look_claims", ["pack_id"], schema=S)
    op.create_table(
        "scene_bindings",
        sa.Column("booster_key", sa.String(64), nullable=False),
        sa.Column("element_id", sa.Uuid(), nullable=False),
        sa.Column("bound_by", sa.Uuid(), nullable=True),
        sa.Column("bound_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("booster_key", name="pk_scene_bindings"),
        schema=S,
    )
    op.create_table(
        "registry_epoch",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("epoch", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", name="pk_registry_epoch"),
        schema=S,
    )
    op.execute('INSERT INTO "visuals".registry_epoch (id, epoch) VALUES (1, 0)')


def downgrade() -> None:
    op.execute(f'DROP SCHEMA IF EXISTS "{S}" CASCADE')
