"""cards — a work's main genre, and a copy in its booster's signature frame (issues 295, 296)

Revision ID: cards_0020
Revises: cards_0019
Create Date: 2026-10-31 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cards_0020"
down_revision: str | Sequence[str] | None = "cards_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VARIANTS = "('normal', 'foil', 'borderless', 'borderless_foil', 'showcase', 'showcase_foil', 'hd', 'genre', 'genre_foil')"
SIGNATURE = "^signature(_foil)?:[a-z0-9-]{1,32}$"
# the main genre of a work's genres as they were when this ran (``family.py``'s ``MAIN``, frozen here)
MAIN = {
    "action": "action",
    "action & adventure": "action",
    "aventure": "adventure",
    "animation": "animation",
    "comédie": "comedy",
    "crime": "crime",
    "documentaire": "documentary",
    "news": "documentary",
    "reality": "documentary",
    "talk": "documentary",
    "drame": "drama",
    "soap": "drama",
    "téléfilm": "drama",
    "familial": "family",
    "kids": "family",
    "fantastique": "fantasy",
    "histoire": "history",
    "horreur": "horror",
    "musique": "music",
    "mystère": "mystery",
    "romance": "romance",
    "science-fiction": "sf",
    "science-fiction & fantastique": "sf",
    "thriller": "thriller",
    "guerre": "war",
    "war & politics": "war",
    "western": "western",
}


def upgrade() -> None:
    op.add_column(
        "sets", sa.Column("genre", sa.String(16), nullable=False, server_default="drama"), schema="cards"
    )
    sets = sa.table(
        "sets", sa.column("key", sa.String), sa.column("facts"), sa.column("genre", sa.String), schema="cards"
    )
    bind = op.get_bind()
    for key, facts in bind.execute(sa.select(sets.c.key, sets.c.facts)).all():
        names = [str(g).strip().lower() for g in (facts or {}).get("genres") or [] if g]
        genre = next((MAIN[n] for n in names if n in MAIN), "drama")
        if genre != "drama":
            bind.execute(sa.update(sets).where(sets.c.key == key).values(genre=genre))
    op.execute("ALTER TABLE cards.copies DROP CONSTRAINT ck_copies_variant")
    op.execute("ALTER TABLE cards.copies ALTER COLUMN variant TYPE varchar(48)")
    op.execute(
        f"ALTER TABLE cards.copies ADD CONSTRAINT ck_copies_variant CHECK (variant IN {VARIANTS} OR variant ~ '{SIGNATURE}')"
    )


def downgrade() -> None:
    op.execute("UPDATE cards.copies SET variant = 'normal' WHERE variant LIKE 'signature:%'")
    op.execute("UPDATE cards.copies SET variant = 'foil' WHERE variant LIKE 'signature_foil:%'")
    op.execute("ALTER TABLE cards.copies DROP CONSTRAINT ck_copies_variant")
    op.execute("ALTER TABLE cards.copies ALTER COLUMN variant TYPE varchar(16)")
    op.execute(f"ALTER TABLE cards.copies ADD CONSTRAINT ck_copies_variant CHECK (variant IN {VARIANTS})")
    op.drop_column("sets", "genre", schema="cards")
