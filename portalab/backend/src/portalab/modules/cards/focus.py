"""Issue 229: where a card's face is. A portrait or a character's image is framed by a window of its own shape
on each card — wider than the image, or taller: without knowing where the face is, some are cut at the
forehead or the chin. Each image a card shows (its portrait, its character's) is looked at once on the
processor (YuNet, the faces' detector the cards already hold): the centre of its largest face and its height
are kept, as fractions of the image (``None``: no face — a poster, a scene), and the card frames it there, a
cut-out character sized by its face (the same size on every card). The cards
members own first, then the rarest."""

import asyncio
from typing import Any

from sqlalchemy import case, cast, exists, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB

from portalab.capabilities.media import unwrap
from portalab.capabilities.media_core import CARD_SOURCES
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.modules.cards.faces import FaceMatcher, Looked
from portalab.modules.cards.models import Card, Copy

BATCH = 120  # cards looked at a run
log = get_logger("portalab.cards")


def centre(looked: Looked) -> list[float] | None:
    """The centre of the image's largest face and its height, as fractions of the image's width and height."""
    if not looked.faces or not looked.width or not looked.height:
        return None
    x, y, w, h = max(looked.faces, key=lambda face: face.share).box
    return [
        round((x + w / 2) / looked.width, 3),
        round((y + h / 2) / looked.height, 3),
        round(h / looked.height, 3),
    ]


def _unknown(column: Any) -> Any:
    """An image the card shows whose face was not looked for yet."""
    return column.is_not(None) & ~func.coalesce(Card.focus, cast("{}", JSONB)).op("?")(column)


class ArtFocus:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        matcher: FaceMatcher,
        blobs: BlobStore | None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.matcher = matcher
        self.blobs = blobs

    async def run(self, count: int = BATCH) -> int:
        """Look at the next cards' images: how many were looked at."""
        sources = self.capabilities.system_providers(CARD_SOURCES)
        if not sources or not await self.matcher.ready():
            return 0
        owned = exists().where(Copy.card_id == Card.id)
        rank = case(
            (Card.rarity == "legendary", 0), (Card.rarity == "epic", 1), (Card.rarity == "rare", 2), else_=3
        )
        async with self.database.session() as session:
            cards = (
                await session.execute(
                    select(Card.id, Card.art, Card.role_art, Card.focus)
                    .where(
                        Card.retired.is_(False),
                        Card.kind != "title",  # a work's card shows its poster: no face to find
                        or_(_unknown(Card.art), _unknown(Card.role_art)),
                    )
                    .order_by(owned.desc(), rank, Card.score.desc())
                    .limit(count)
                )
            ).all()
        found: dict[Any, dict[str, Any]] = {}
        for card_id, art, role_art, focus in cards:
            known = dict(focus or {})
            for ref in (role_art, art):
                if ref and ref not in known:
                    known[ref] = await self._centre(sources[0].provider, ref)
            found[card_id] = known
        async with self.database.unit_of_work() as uow:
            for card_id, known in found.items():
                card = await uow.session.get(Card, card_id)
                if card is not None:
                    card.focus = known
        if found:
            log.info("cards' faces looked for", extra={"fields": {"cards": len(found)}})
        return len(found)

    async def _centre(self, sources: Any, ref: str) -> list[float] | None:
        try:
            if ref.startswith("blob:"):
                if self.blobs is None:
                    return None
                data = await self.blobs.get(ref.removeprefix("blob:"))
            else:
                data = unwrap(await sources.image(ref, "h632"))
            return centre(await asyncio.to_thread(self.matcher.look, data))
        except Exception:  # an image that cannot be read: no face kept, the card framed as before
            log.debug("card's image not looked at", exc_info=True)
            return None
