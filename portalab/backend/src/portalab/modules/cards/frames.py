"""Issue 230: an actor's character taken from the film itself. When TMDB had no still of them in that film,
the cards ask the media server holding its file (Plex) for still images spread over its length, find the faces
on them (on the processor) and compare each with the portrait of every actor of the set: each actor gets the
image where their own face is the clearest, framed around it, kept in the blob store. One pass over a film
serves all its actors; an animated film is left to the web search (drawn faces cannot be compared). Looked
for once per card (the cache), the rarest sets first, one film at a time in the background."""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import case, func, select, update

from portalab.capabilities.media import VIDEO_FRAMES, unwrap
from portalab.capabilities.media_core import CARD_SOURCES
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.cards.faces import Face, FaceMatcher
from portalab.modules.cards.models import Card, CardSet

COUNT = 96  # images taken over a film (one every minute or two)
FIRST, LAST = 0.06, 0.9  # from just after the opening to before the end credits
ACTORS = 15  # the first actors of a set compared
SAME_ACTOR = 0.4  # a face is theirs above this, and only when it is clearly closer to them than to the others
APART = 0.06  # how much closer to them than to anyone else of the cast
SMALLEST = 70  # a face's height at least (pixels): smaller, it is someone in the background
SHARP = 40.0  # a face's sharpness at least (variance of its Laplacian): a blurred one is passed over
NAMESPACE = "cards"
log = get_logger("portalab.cards")


def moments(count: int = COUNT) -> list[float]:
    step = (LAST - FIRST) / (count - 1)
    return [round(FIRST + i * step, 4) for i in range(count)]


def crop_box(
    face: tuple[int, int, int, int], width: int, height: int, top: int = 0, bottom: int | None = None
) -> tuple[int, int, int, int]:
    """The card's frame around a face: 4:3, head and shoulders, the face at two fifths of its height —
    within the picture (rows ``top`` to ``bottom``: black bars left out), as left, top, width, height."""
    x, y, w, h = face
    bottom = height if bottom is None or bottom <= top else bottom
    room = bottom - top
    crop_h = min(room, max(int(h * 3.2), 360))
    crop_w = int(crop_h * 4 / 3)
    if crop_w > width:
        crop_w = width
        crop_h = min(room, int(crop_w * 3 / 4))
    cx, cy = x + w / 2, y + h / 2
    left = int(min(max(cx - crop_w / 2, 0), width - crop_w))
    upper = int(min(max(cy - crop_h * 0.4, top), bottom - crop_h))
    return left, upper, crop_w, crop_h


@dataclass(frozen=True, slots=True)
class Pick:
    value: float
    frame: int
    box: tuple[int, int, int, int]


def value_of(similarity: float, face: Face, faces: int) -> float | None:
    """How good this face is as that actor's image (``None``: not them, or too small)."""
    if similarity < SAME_ACTOR or face.box[3] < SMALLEST:
        return None
    return similarity + 0.25 * min(1.0, face.box[3] / 220) - 0.08 * max(0, faces - 2)


def assign(
    portraits: dict[Any, Face], frames: Sequence[Sequence[Face]], similar: Callable[[Face, Face], float]
) -> dict[Any, Pick]:
    """Each actor's best image: the frame where their own face is the clearest — a face counts for the actor
    it resembles most, and only clearly more than any other actor of the cast (look-alikes left out)."""
    best: dict[Any, Pick] = {}
    for index, faces in enumerate(frames):
        for face in faces:
            ranked = sorted(((similar(p, face), card) for card, p in portraits.items()), key=lambda r: -r[0])
            if not ranked or (len(ranked) > 1 and ranked[0][0] - ranked[1][0] < APART):
                continue
            similarity, card = ranked[0]
            value = value_of(similarity, face, len(faces))
            if value is not None and (card not in best or value > best[card].value):
                best[card] = Pick(value, index, face.box)
    return best


class FilmFrames:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        matcher: FaceMatcher,
        blobs: BlobStore | None,
        *,
        clock: Clock | None = None,
        enabled: Callable[[], bool] = lambda: True,
        characters_first: Callable[[], bool] = lambda: False,
    ) -> None:
        self.characters_first = characters_first
        self.database = database
        self.capabilities = capabilities
        self.matcher = matcher
        self.blobs = blobs
        self.clock = clock
        self.enabled = enabled

    def available(self) -> bool:
        """A media server can take images of a film, and the administrator lets the cards ask."""
        return bool(
            self.enabled() and self.blobs is not None and self.capabilities.system_providers(VIDEO_FRAMES)
        )

    async def run(self, films: int = 1, *, set_key: str | None = None) -> int:
        """Take the images of the next film(s) and give its actors theirs: how many cards got one.
        ``set_key``: that set now (its characters looked for again), its cards still without one."""
        sources = self.capabilities.system_providers(CARD_SOURCES)
        if not sources or not self.available() or not await self.matcher.ready():
            return 0  # nothing to take them with: nothing marked, looked for once there is
        rank = case(
            (Card.rarity == "legendary", 0), (Card.rarity == "epic", 1), (Card.rarity == "rare", 2), else_=3
        )
        wanted = (
            (Card.role_art.is_(None),)
            if set_key
            else (
                Card.role_art.is_(None),
                Card.role_checked_at.is_not(None),
                Card.frame_checked_at.is_(None),
                # issue 231: the community database first, when there is one
                *((Card.character_checked_at.is_not(None),) if self.characters_first() else ()),
            )
        )
        async with self.database.session() as session:
            sets = (
                await session.execute(
                    select(CardSet.key, CardSet.object_id, CardSet.kind, CardSet.animated)
                    .join(Card, Card.set_key == CardSet.key)
                    .where(
                        Card.kind == "cast",
                        Card.retired.is_(False),
                        CardSet.present.is_(True),
                        *((CardSet.key == set_key,) if set_key else ()),
                        *wanted,
                    )
                    .group_by(CardSet.key)
                    .order_by(func.min(rank), func.max(Card.score).desc())
                    .limit(films)
                )
            ).all()
        given = 0
        for key, object_id, kind, animated in sets:
            if animated or kind != "movie":
                await self._mark(key, wanted)  # drawn faces, or a series: left to the web search
                continue
            try:
                given += await self._film(sources[0].provider, key, object_id, wanted)
            except Exception:  # the server or a portrait fails: taken again next time
                log.warning("film's images not taken", exc_info=True)
        return given

    async def _film(self, sources: Any, key: str, object_id: Any, wanted: tuple[Any, ...]) -> int:
        async with self.database.session() as session:
            cards = (
                await session.execute(
                    select(Card.id, Card.art)
                    .where(Card.set_key == key, Card.kind == "cast", Card.retired.is_(False), *wanted)
                    .order_by(Card.billing)
                    .limit(ACTORS)
                )
            ).all()
        portraits: dict[Any, Face] = {}
        for card_id, art in cards:
            if not art:
                continue
            looked = await self._look(unwrap(await sources.image(art, "h632")))
            if len(looked.faces) == 1:
                portraits[card_id] = looked.faces[0]
        images = await sources.frames(object_id, moments()) if portraits else []
        if images is None:
            await self._mark(key, wanted)  # its file is on no server that can take images
            return 0
        frames = [await self._look(image) for image in images]
        sharp = [[f for f in looked.faces if f.sharpness >= SHARP] for looked in frames]
        picks = assign(portraits, sharp, self.matcher.similarity)
        stored: dict[Any, str] = {}
        for card_id, pick in picks.items():
            looked = frames[pick.frame]
            jpeg = await asyncio.to_thread(
                self._crop,
                images[pick.frame],
                crop_box(pick.box, looked.width, looked.height, looked.top, looked.bottom or None),
            )
            if jpeg is not None and self.blobs is not None:
                stored[card_id] = (await self.blobs.put(NAMESPACE, jpeg, content_type="image/jpeg")).key
        async with self.database.unit_of_work() as uow:
            for card_id, blob in stored.items():
                card = await uow.session.get(Card, card_id)
                if card is not None:
                    card.role_art = f"blob:{blob}"
                    card.frame_checked_at = utc_now(self.clock)
        await self._mark(key, wanted)
        log.info(
            "film's images taken", extra={"fields": {"set": key, "frames": len(images), "given": len(stored)}}
        )
        return len(stored)

    async def _mark(self, key: str, wanted: tuple[Any, ...]) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                update(Card)
                .where(Card.set_key == key, Card.kind == "cast", Card.retired.is_(False), *wanted)
                .values(frame_checked_at=utc_now(self.clock))
                .execution_options(synchronize_session=False)
            )

    async def _look(self, data: bytes) -> Any:
        return await asyncio.to_thread(self.matcher.look, data)

    def _crop(self, data: bytes, box: tuple[int, int, int, int]) -> bytes | None:
        return self.matcher.crop(data, box)
