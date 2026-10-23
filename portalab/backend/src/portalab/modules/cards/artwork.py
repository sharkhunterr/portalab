"""Issue 229: a work's card has its borderless alternative drawn from an art site (fanart.tv) — the work's
art without any text on it, the best liked — a textless poster (upright, like the card), else a background,
else a thumb — and (issue 234) its title drawn, its logos per language, for its boosters. Looked for in the
background, the rarest works first, a few at a time; kept once looked for (the cache), looked for again when
the set is made again and its card new. Without one, the borderless card shows a backdrop of the work
(TMDB)."""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import case, select

from portalab.capabilities.media import ARTWORK, Artwork, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.cards.models import Card, CardSet

BATCH = 60  # works looked for at a time
# a card stands upright: a textless poster (key art, the card's own shape) first, then a background
KIND_ORDER = {"poster": 0, "background": 1, "thumb": 2}
log = get_logger("portalab.cards")


def best_art(found: Sequence[Artwork]) -> str | None:
    """The full art of a work's card: with no text on it, the best liked — a poster (the card's shape), else
    a background, else a thumb."""
    textless = [a for a in found if a.kind in KIND_ORDER and a.lang is None]
    ordered = sorted(textless, key=lambda a: (KIND_ORDER[a.kind], -a.likes))
    return ordered[0].image if ordered else None


def best_logos(found: Sequence[Artwork]) -> dict[str, str]:
    """Issue 234: the work's title drawn — its best liked logo per language (``""``: without one)."""
    out: dict[str, tuple[int, str]] = {}
    for art in found:
        if art.kind != "logo":
            continue
        lang = (art.lang or "")[:2]
        if lang not in out or art.likes > out[lang][0]:
            out[lang] = (art.likes, art.image)
    return {lang: image for lang, (_, image) in out.items()}


def parse_ids(raw: str | None) -> Mapping[str, str]:
    pairs = (item.split(":", 1) for item in (raw or "").split(",") if ":" in item)
    return {scheme: value for scheme, value in pairs}


class FanArt:
    def __init__(
        self, database: Database, capabilities: CapabilityRegistry, *, clock: Clock | None = None
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.clock = clock

    async def run(self, batch: int = BATCH) -> int:
        """Look for the next works' full art (the rarest first): how many cards got one."""
        providers = self.capabilities.system_providers(ARTWORK)
        if not providers:
            return 0  # no art site connected: nothing is marked, looked for once one is
        provider: Any = providers[0].provider
        rank = case(
            (Card.rarity == "legendary", 0), (Card.rarity == "epic", 1), (Card.rarity == "rare", 2), else_=3
        )
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Card.id, CardSet.key, CardSet.kind, CardSet.ids)
                    .join(CardSet, CardSet.key == Card.set_key)
                    .where(
                        Card.kind == "title",
                        Card.retired.is_(False),
                        Card.fan_checked_at.is_(None),
                        CardSet.present.is_(True),
                        CardSet.ids.is_not(None),
                    )
                    .order_by(rank, Card.score.desc())
                    .limit(batch)
                )
            ).all()
        given = 0
        for card_id, set_key, kind, ids in rows:
            try:
                found = unwrap(await provider.artwork(kind, parse_ids(ids)))
            except Exception:  # the art site does not answer: looked for again next time
                log.warning("art not found", exc_info=True)
                continue
            art = best_art(found or [])
            async with self.database.unit_of_work() as uow:
                card = await uow.session.get(Card, card_id)
                if card is not None:
                    card.fan_art = art
                    card.fan_checked_at = utc_now(self.clock)
                card_set = await uow.session.get(CardSet, set_key)
                if card_set is not None:
                    card_set.logos = best_logos(found or []) or None
            given += 1 if art else 0
        return given
