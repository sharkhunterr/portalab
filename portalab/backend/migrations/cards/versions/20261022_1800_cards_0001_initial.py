"""cards schema — sets made from the works present, their cards, the copies members own and the packs they
were given (issue 229)

Revision ID: cards_0001
Revises:
Create Date: 2026-10-22 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "cards_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("cards",)
depends_on: str | Sequence[str] | None = ("core_0005", "identity_0001")

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "cards"')
    op.create_table(
        "sets",
        sa.Column("key", sa.String(48), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(8), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("country", sa.String(8), nullable=True),
        sa.Column("poster", sa.String(120), nullable=True),
        sa.Column("saga", sa.String(200), nullable=True),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("generated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_sets"),
        sa.UniqueConstraint("object_id", name="uq_sets_object_id"),
        schema="cards",
    )
    op.create_table(
        "cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("set_key", sa.String(48), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("ident", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("person_ref", sa.String(160), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(200), nullable=True),
        sa.Column("flavor", sa.String(300), nullable=True),
        sa.Column("art", sa.String(120), nullable=True),
        sa.Column("alt_art", sa.String(120), nullable=True),
        sa.Column("billing", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rarity", sa.String(12), nullable=False),
        sa.Column("retired", sa.Boolean(), nullable=False),
        sa.Column("updated_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_cards"),
        sa.ForeignKeyConstraint(
            ["set_key"], ["cards.sets.key"], name="fk_cards_set_key_sets", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("set_key", "ident", name="uq_cards_set_ident"),
        sa.UniqueConstraint("set_key", "number", name="uq_cards_set_number"),
        sa.CheckConstraint("rarity IN ('common', 'rare', 'epic', 'legendary')", name="ck_cards_rarity"),
        schema="cards",
    )
    op.create_index("ix_cards_person", "cards", ["person_ref"], schema="cards")
    op.create_table(
        "packs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("set_key", sa.String(48), nullable=True),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("given_at", TZ, nullable=False),
        sa.Column("opened_at", TZ, nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_packs"),
        sa.UniqueConstraint("idempotency_key", name="uq_packs_idempotency"),
        sa.ForeignKeyConstraint(["user_id"], ["identity.users.id"], name="fk_packs_user", ondelete="CASCADE"),
        schema="cards",
    )
    op.create_index("ix_packs_user_opened", "packs", ["user_id", "opened_at"], schema="cards")
    op.create_table(
        "copies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Uuid(), nullable=False),
        sa.Column("variant", sa.String(16), nullable=False),
        sa.Column("pack_id", sa.Uuid(), nullable=True),
        sa.Column("acquired_at", TZ, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_copies"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.users.id"], name="fk_copies_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["card_id"], ["cards.cards.id"], name="fk_copies_card_id_cards", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["pack_id"], ["cards.packs.id"], name="fk_copies_pack_id_packs", ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "variant IN ('normal', 'foil', 'borderless', 'borderless_foil')", name="ck_copies_variant"
        ),
        schema="cards",
    )
    op.create_index("ix_copies_user_card", "copies", ["user_id", "card_id"], schema="cards")


def downgrade() -> None:
    for table in ("copies", "packs", "cards", "sets"):
        op.drop_table(table, schema="cards")
    op.execute('DROP SCHEMA IF EXISTS "cards"')
