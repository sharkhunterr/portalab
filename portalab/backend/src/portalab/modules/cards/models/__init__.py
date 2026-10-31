"""Schema ``cards`` (issue 229): a set per work present (a film, a series), its cards — the work itself, who
made it, who plays in it — numbered like a trading card game's, with a rarity; the copies members own, in
their version (normal, foil, borderless, borderless foil, their edition's, foil or not); and the packs they
were given, opened or not."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from portalab.core.db import TZDateTime, schema_metadata
from portalab.core.ids import new_id
from portalab.core.privacy_registry import not_personal

RARITIES = ("common", "rare", "epic", "legendary")
# issue 255: "hd", a legendary's HD version; issue 295: "genre", its genre's frame
VARIANTS = (
    "normal",
    "foil",
    "borderless",
    "borderless_foil",
    "showcase",
    "showcase_foil",
    "hd",
    "genre",
    "genre_foil",
)
# issue 296: a copy in the signature frame of the booster it came from: its look, as the booster names it
SIGNATURE_PATTERN = "^signature(_foil)?:[a-z0-9-]{1,32}$"


class CardsBase(DeclarativeBase):
    metadata = schema_metadata("cards")


class CardSet(CardsBase):
    """A work present in the catalog, as a set of cards: its code (three letters, like a set's symbol)."""

    __tablename__ = "sets"

    key: Mapped[str] = mapped_column(String(48), primary_key=True)  # the work's object id
    object_id: Mapped[UUID] = mapped_column(nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("a work's title"))
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    country: Mapped[str | None] = mapped_column(String(8))
    poster: Mapped[str | None] = mapped_column(String(120), info=not_personal("an artwork reference"))
    # a scene of the work: behind its people's portraits on their cards
    backdrop: Mapped[str | None] = mapped_column(String(120), info=not_personal("an artwork reference"))
    # an animated work: its characters are drawn (no face to compare)
    animated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # the cards' colour by the work's genre (``family.py``) and its figures printed on them, frozen when the
    # set is made: rating, votes, budget, revenue, runtime, seasons, director
    family: Mapped[str] = mapped_column(String(12), nullable=False, default="drama", server_default="drama")
    # issue 295: its main genre (``family.py``: the first of its genres that has a frame) — its genre frame's
    # and its genre booster's
    genre: Mapped[str] = mapped_column(String(16), nullable=False, default="drama", server_default="drama")
    # issue 296: its themes (``family.py``), the most telling first — its theme booster's, its booster's scene
    themes: Mapped[list[str]] = mapped_column(
        ARRAY(String(16)), nullable=False, default=list, server_default="{}"
    )
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    saga: Mapped[str | None] = mapped_column(String(200), info=not_personal("a saga's name"))
    # issue 234: the work's title drawn (an art site's HD logo), the best liked per language (``""``: none)
    logos: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    tmdb: Mapped[str | None] = mapped_column(String(24))  # the work's TMDB id
    ids: Mapped[str | None] = mapped_column(String(240))  # every id known, ``scheme:value`` comma-separated
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Card(CardsBase):
    """One card of a set: ``ident`` keeps it the same card when its set is generated again (its number
    too); ``retired`` when the work no longer credits it (owned copies stay)."""

    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint("set_key", "ident", name="uq_cards_set_ident"),
        UniqueConstraint("set_key", "number", name="uq_cards_set_number"),
        CheckConstraint(f"rarity IN {RARITIES}", name="rarity"),
        Index("ix_cards_person", "person_ref"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    set_key: Mapped[str] = mapped_column(ForeignKey("cards.sets.key", ondelete="CASCADE"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    ident: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("a card's identity"))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # title, cast, director, creator…
    person_ref: Mapped[str | None] = mapped_column(String(160), info=not_personal("a credited person"))
    name: Mapped[str] = mapped_column(String(200), nullable=False, info=not_personal("a card's name"))
    role: Mapped[str | None] = mapped_column(String(200), info=not_personal("a character or a job"))
    flavor: Mapped[str | None] = mapped_column(String(300), info=not_personal("a tagline"))
    art: Mapped[str | None] = mapped_column(String(120), info=not_personal("an artwork reference"))
    alt_art: Mapped[str | None] = mapped_column(String(120), info=not_personal("an artwork reference"))
    # an actor's character in this very work: two images (the card's, its borderless alternative's), looked
    # for once (``role_checked_at``) — the cache
    role_art: Mapped[str | None] = mapped_column(String(120), info=not_personal("an artwork reference"))
    role_alt: Mapped[str | None] = mapped_column(String(120), info=not_personal("an artwork reference"))
    role_checked_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    # a work's card: its full art from an art site (fanart.tv), for the borderless alternative — the cache
    fan_art: Mapped[str | None] = mapped_column(String(240), info=not_personal("an artwork reference"))
    fan_checked_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    # an actor's character looked for on the web (when TMDB had none) — the cache
    search_checked_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    # issue 230: an actor's character taken from the film's own video (its faces compared) — the cache
    frame_checked_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    # issue 231: the role's own image from a community database (TheTVDB) — the cache
    character_checked_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    # where the face is in each image it shows: {its reference: [x, y, height] as fractions, or null}
    focus: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # its character cut out of the image it shows: {its reference: the cut-out's (``blob:``), or null}
    cutout: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    billing: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rarity: Mapped[str] = mapped_column(String(12), nullable=False, default="common")
    retired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Copy(CardsBase):
    """A copy a member owns, in its version (one row each: a trade will move it)."""

    __tablename__ = "copies"
    __table_args__ = (
        # issue 296: or a booster's signature frame (``signature:<its look>``, foil or not)
        CheckConstraint(f"variant IN {VARIANTS} OR variant ~ '{SIGNATURE_PATTERN}'", name="variant"),
        Index("ix_copies_user_card", "user_id", "card_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)  # FK identity.users (DB), CASCADE: erased with them
    card_id: Mapped[UUID] = mapped_column(ForeignKey("cards.cards.id", ondelete="CASCADE"), nullable=False)
    variant: Mapped[str] = mapped_column(String(48), nullable=False)
    pack_id: Mapped[UUID | None] = mapped_column(ForeignKey("cards.packs.id", ondelete="SET NULL"))
    acquired_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class Pack(CardsBase):
    """A pack given to a member (a work watched to the end…): its cards are drawn when given, revealed when
    opened."""

    __tablename__ = "packs"
    __table_args__ = (
        Index("ix_packs_user_opened", "user_id", "opened_at"),
        UniqueConstraint("idempotency_key", name="uq_packs_idempotency"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[UUID] = mapped_column(nullable=False)  # FK identity.users (DB), CASCADE: erased with them
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # watched, wheel, admin…
    set_key: Mapped[str | None] = mapped_column(String(48))  # the work it came from
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    given_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    opened_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
