"""Issue 229: an actor's character found on the web — when TMDB had no still of them in that work, the cards
ask a self-hosted metasearch (SearXNG) for « actor character film », fetch the first images, and keep the best
one where **the actor's own face** (compared with their TMDB portrait, on the processor) is seen and whose
page names the character or the film (never a premiere, a festival, an interview). Kept in the blob store,
served by the cards; looked for once per card (the cache), the rarest first, a few at a time. Without one,
the card keeps the actor's portrait."""

import asyncio
import re
from typing import Any

from sqlalchemy import case, select

from portalab.capabilities.media import IMAGE_SEARCH, unwrap
from portalab.capabilities.media_core import CARD_SOURCES
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.cards.faces import EVENT, SKIPPED_ENGINES, Candidate, FaceMatcher, score
from portalab.modules.cards.models import Card, CardSet

BATCH = 6  # cards looked for at a time
FETCHED = 10  # images fetched per card at most
NAMESPACE = "cards"
log = get_logger("portalab.cards")


def query_for(name: str, character: str | None, film: str) -> str:
    """« Tom Cruise Pete Maverick Mitchell Top Gun Maverick »: a character's ranks and quotes left out."""
    role = re.sub(r"\b(capt|lt|cmdr|adm|col|sgt|dr|mr|mrs|ms|wo-\d)\.?\s", " ", character or "", flags=re.I)
    role = re.sub(r"[\"'()\u2018\u2019\u201c\u201d]", " ", role)
    return " ".join(f"{name} {role} {film}".split())[:200]


def image_type(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


class RoleSearch:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        matcher: FaceMatcher,
        blobs: BlobStore | None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.matcher = matcher
        self.blobs = blobs
        self.clock = clock

    def _providers(self) -> tuple[Any, Any] | None:
        search = self.capabilities.system_providers(IMAGE_SEARCH)
        sources = self.capabilities.system_providers(CARD_SOURCES)
        if not search or not sources or self.blobs is None:
            return None
        return search[0].provider, sources[0].provider

    async def run(self, batch: int = BATCH) -> int:
        """Look for the next cards' characters on the web: how many got one."""
        found = self._providers()
        if found is None or not await self.matcher.ready():
            return 0  # nothing to search with: nothing marked, looked for once there is
        search, sources = found
        rank = case(
            (Card.rarity == "legendary", 0), (Card.rarity == "epic", 1), (Card.rarity == "rare", 2), else_=3
        )
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Card.id, Card.name, Card.role, Card.art, CardSet.name)
                    .join(CardSet, CardSet.key == Card.set_key)
                    .where(
                        Card.kind == "cast",
                        Card.retired.is_(False),
                        Card.role_art.is_(None),
                        Card.role_checked_at.is_not(None),  # TMDB was asked first
                        Card.search_checked_at.is_(None),
                        CardSet.present.is_(True),
                    )
                    .order_by(rank, Card.score.desc())
                    .limit(batch)
                )
            ).all()
        given = 0
        for card_id, name, role, art, film in rows:
            try:
                chosen = await self._one(search, sources, name, role, art, film)
            except Exception:  # a search or a portrait that fails: looked for again next time
                log.warning("character not looked for", exc_info=True)
                continue
            async with self.database.unit_of_work() as uow:
                card = await uow.session.get(Card, card_id)
                if card is None:
                    continue
                card.search_checked_at = utc_now(self.clock)
                if chosen is not None:
                    card.role_art = f"blob:{chosen}"
                    given += 1
        return given

    async def _one(
        self, search: Any, sources: Any, name: str, role: str | None, art: str | None, film: str
    ) -> str | None:
        if not art:
            return None
        portrait = await self.matcher_look(unwrap(await sources.image(art, "h632")))
        if len(portrait.faces) != 1:
            return None  # no portrait to compare with
        hits = unwrap(await search.images(query_for(name, role, film), 30)) or []
        hits = [h for h in hits if h.engine not in SKIPPED_ENGINES and not EVENT.search(h.title)][:FETCHED]
        best: tuple[float, bytes] | None = None
        for hit in hits:
            try:
                data = unwrap(await search.fetch(hit.url))
            except Exception:  # noqa: S112 — an image that cannot be fetched is skipped
                continue
            looked = await self.matcher_look(data)
            if not looked.faces:
                continue
            similarity = max(self.matcher.similarity(portrait.faces[0], face) for face in looked.faces)
            value = score(
                Candidate(hit.url, hit.title, hit.engine, similarity, looked.width, looked.height), role, film
            )
            if value is not None and (best is None or value > best[0]):
                best = (value, data)
        if best is None or self.blobs is None:
            return None
        stored = await self.blobs.put(NAMESPACE, best[1], content_type=image_type(best[1]))
        return stored.key

    async def matcher_look(self, data: bytes) -> Any:
        return await asyncio.to_thread(self.matcher.look, data)
