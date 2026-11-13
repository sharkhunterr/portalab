"""Issue 229: an actor's character found on the web — when TMDB had no still of them in that work, the cards
ask a self-hosted metasearch (SearXNG) for « actor character film », fetch the first images, and keep the best
one where **the actor's own face** (compared with their TMDB portrait, on the processor) is seen and whose
page names the character or the film (never a premiere, a festival, an interview). Kept in the blob store,
served by the cards; looked for once per card (the cache), the rarest first, a few at a time. Without one,
the card keeps the actor's portrait."""

import asyncio
import re
from collections.abc import Callable
from typing import Any

from sqlalchemy import case, or_, select

from portalab.capabilities.media import IMAGE_SEARCH, unwrap
from portalab.capabilities.media_core import CARD_SOURCES
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.cards.faces import EVENT, SAME_PERSON, SKIPPED_ENGINES, Candidate, FaceMatcher, score
from portalab.modules.cards.models import Card, CardSet

BATCH = 6  # cards looked for at a time
FETCHED = 10  # images fetched per card at most
NAMESPACE = "cards"
log = get_logger("portalab.cards")


def query_for(name: str | None, character: str | None, film: str) -> str:
    """« Tom Cruise Pete Maverick Mitchell Top Gun Maverick »: a character's ranks, quotes and « (voice) »
    left out; an animated work's without the actor (« Woody Toy Story »)."""
    role = re.sub(
        r"\b(capt|lt|cmdr|adm|col|sgt|dr|mr|mrs|ms|wo-\d)\.?\s", " ", character or "", flags=re.IGNORECASE
    )
    role = re.sub(r"\((voice|voix|uncredited)\)", " ", role, flags=re.IGNORECASE)
    role = re.sub(r"[\"'()\u2018\u2019\u201c\u201d]", " ", role)
    return " ".join(f"{name or ''} {role} {film}".split())[:200]


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
        face_check: Callable[[], bool] = lambda: True,
        frames_first: Callable[[], bool] = lambda: False,
        enabled: Callable[[], bool] = lambda: True,
    ) -> None:
        self.enabled = enabled
        self.face_check = face_check
        self.frames_first = frames_first
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

    async def run(self, batch: int = BATCH, *, set_key: str | None = None) -> int:
        """Look for the next cards' characters on the web: how many got one. ``set_key``: that set's cards
        still without one, now (its characters looked for again)."""
        found = self._providers()
        if found is None or not self.enabled():  # 231: the web is an option the administrator turns on
            return 0  # nothing to search with: nothing marked, looked for once there is
        check = self.face_check()
        search, sources = found
        rank = case(
            (Card.rarity == "legendary", 0), (Card.rarity == "epic", 1), (Card.rarity == "rare", 2), else_=3
        )
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Card.id, Card.name, Card.role, Card.art, CardSet.name, CardSet.animated)
                    .join(CardSet, CardSet.key == Card.set_key)
                    .where(
                        Card.kind == "cast",
                        Card.retired.is_(False),
                        CardSet.present.is_(True),
                        *(
                            (CardSet.key == set_key, Card.role_art.is_(None))
                            if set_key
                            else (
                                Card.role_art.is_(None),
                                Card.role_checked_at.is_not(None),  # TMDB was asked first
                                Card.search_checked_at.is_(None),
                                # issue 230: the film itself next, when a media server can show it
                                *(
                                    (
                                        or_(
                                            Card.frame_checked_at.is_not(None),
                                            CardSet.animated.is_(True),
                                            CardSet.kind != "movie",
                                        ),
                                    )
                                    if self.frames_first()
                                    else ()
                                ),
                            )
                        ),
                    )
                    .order_by(rank, Card.score.desc())
                    .limit(batch)
                )
            ).all()
        given = 0
        for card_id, name, role, art, film, animated in rows:
            if check and not animated and not await self.matcher.ready():
                continue  # the faces cannot be compared (no model): not marked, looked for again later
            try:
                if check and not animated:
                    chosen = await self._one(search, sources, name, role, art, film)
                else:  # a drawn character, or the check switched off: the page must name the character
                    chosen = await self._named(search, None if animated else name, role, film)
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
            similarities = [self.matcher.similarity(portrait.faces[0], face) for face in looked.faces]
            if sum(1 for s in similarities if s >= SAME_PERSON) > 1:
                continue  # the actor twice: a « then and now » montage, not a scene
            similarity = max(similarities)
            value = score(
                Candidate(hit.url, hit.title, hit.engine, similarity, looked.width, looked.height), role, film
            )
            if value is not None and (best is None or value > best[0]):
                best = (value, data)
        if best is None or self.blobs is None:
            return None
        stored = await self.blobs.put(NAMESPACE, best[1], content_type=image_type(best[1]))
        return stored.key

    async def _named(self, search: Any, name: str | None, role: str | None, film: str) -> str | None:
        """Without faces: the best image whose page names the character (and the work), the first that
        can be fetched."""
        if not role:
            return None
        hits = unwrap(await search.images(query_for(name, role, film), 30)) or []
        ranked = sorted(
            (
                (value, hit)
                for hit in hits
                if (
                    value := score(
                        Candidate(hit.url, hit.title, hit.engine, 0.0, hit.width, hit.height),
                        role,
                        film,
                        faces=False,
                        actor=name,
                    )
                )
                is not None
            ),
            key=lambda pair: -pair[0],
        )
        for _, hit in ranked[:FETCHED]:
            try:
                data = unwrap(await search.fetch(hit.url))
            except Exception:  # noqa: S112 — an image that cannot be fetched is skipped
                continue
            if self.blobs is None:
                return None
            stored = await self.blobs.put(NAMESPACE, data, content_type=image_type(data))
            return stored.key
        return None

    async def matcher_look(self, data: bytes) -> Any:
        return await asyncio.to_thread(self.matcher.look, data)
