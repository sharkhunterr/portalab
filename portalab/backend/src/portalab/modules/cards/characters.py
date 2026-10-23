"""Issue 231: an actor's card shows the character itself, from a community database (TheTVDB) that keeps one
image per role — in costume, made up, drawn: what neither a face nor a search finds. Looked for work by work
(one call for its whole cast), the rarest first, a few works at a time in the background; it comes first —
its image wins over any other — and is kept once found (the cache). A role is matched by its actor's name,
else by the character's."""

import re
import unicodedata
from collections.abc import Sequence
from typing import Any

from sqlalchemy import case, func, select, update

from portalab.capabilities.media import CHARACTERS, CharacterImage, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.cards.artwork import parse_ids
from portalab.modules.cards.models import Card, CardSet
from portalab.modules.cards.search import image_type

BATCH = 12  # works looked for at a time
NAMESPACE = "cards"
log = get_logger("portalab.cards")


def norm(text: str | None) -> str:
    """A name as compared: no accents, no case, no punctuation, no « (voice) »."""
    text = re.sub(r"\((voice|voix|uncredited)\)", " ", text or "", flags=re.I)
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def match(cards: Sequence[tuple[Any, str, str | None]], found: Sequence[CharacterImage]) -> dict[Any, str]:
    """Each card's role image: the one of its actor (by name), else of its character — each image once."""
    by_person = {norm(c.person): c for c in reversed(found)}
    by_character = {norm(c.character): c for c in reversed(found) if c.character}
    out: dict[Any, str] = {}
    used: set[str] = set()
    for card_id, name, role in cards:
        hit = by_person.get(norm(name)) or by_character.get(norm(role) or "\0")
        if hit is not None and hit.image not in used:
            out[card_id] = hit.image
            used.add(hit.image)
    return out


class CharacterSheets:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        blobs: BlobStore | None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.blobs = blobs
        self.clock = clock

    def available(self) -> bool:
        return self.blobs is not None and bool(self.capabilities.system_providers(CHARACTERS))

    async def run(self, batch: int = BATCH, *, set_key: str | None = None) -> int:
        """Look for the next works' roles: how many cards got their character. ``set_key``: that set now (an
        administrator's request), looked for again."""
        providers = self.capabilities.system_providers(CHARACTERS)
        if not providers or self.blobs is None:
            return 0  # nothing to ask: nothing marked, looked for once there is
        provider = providers[0].provider
        rank = case(
            (Card.rarity == "legendary", 0), (Card.rarity == "epic", 1), (Card.rarity == "rare", 2), else_=3
        )
        async with self.database.session() as session:
            sets = (
                await session.execute(
                    select(CardSet.key, CardSet.kind, CardSet.ids, CardSet.tmdb)
                    .join(Card, Card.set_key == CardSet.key)
                    .where(
                        Card.kind == "cast",
                        Card.retired.is_(False),
                        CardSet.present.is_(True),
                        *((CardSet.key == set_key,) if set_key else (Card.character_checked_at.is_(None),)),
                    )
                    .group_by(CardSet.key)
                    .order_by(func.min(rank), func.max(Card.score).desc())
                    .limit(batch)
                )
            ).all()
        given = 0
        for key, kind, raw_ids, tmdb in sets:
            ids = dict(parse_ids(raw_ids))
            if tmdb and "tmdb" not in ids:
                ids["tmdb"] = tmdb
            try:
                found = unwrap(await provider.characters(kind, ids))
            except Exception:  # the database does not answer: looked for again next time
                log.warning("roles' images not found", exc_info=True)
                continue
            if found is None:
                continue
            given += await self._give(provider, key, found)
        return given

    async def _give(self, provider: Any, key: str, found: Sequence[CharacterImage]) -> int:
        async with self.database.session() as session:
            cards = (
                await session.execute(
                    select(Card.id, Card.name, Card.role)
                    .where(Card.set_key == key, Card.kind == "cast", Card.retired.is_(False))
                    .order_by(Card.billing)
                )
            ).all()
        stored: dict[Any, str] = {}
        for card_id, ref in match([tuple(c) for c in cards], found).items():
            try:
                data = unwrap(await provider.fetch_character(ref))
            except Exception:  # noqa: S112 — an image that cannot be fetched: the next sources try
                continue
            if data and self.blobs is not None:
                stored[card_id] = (await self.blobs.put(NAMESPACE, data, content_type=image_type(data))).key
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            for card_id, blob in stored.items():
                card = await uow.session.get(Card, card_id)
                if card is not None:
                    card.role_art = f"blob:{blob}"
            await uow.session.execute(
                update(Card)
                .where(Card.set_key == key, Card.kind == "cast", Card.retired.is_(False))
                .values(character_checked_at=now)
                .execution_options(synchronize_session=False)
            )
        return len(stored)
