"""Issue 229: an actor's card shows their character in that very work — an image they are tagged in (TMDB),
from that film or series: a still first, else a backdrop, the best liked, and another for the borderless
alternative; never a poster (it is tagged with the whole cast but shows its lead), never an image of the work
(it shows someone else): without one, their own portrait. Looked for person by person (one call each, every
work of theirs at once), the rarest cards first, a few people at a time in the background; kept once found
(the cache: looked for again only when the set is made again and the card is new)."""

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import case, func, select

from portalab.capabilities.media_core import CARD_SOURCES, CardImage
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.cards.models import Card, CardSet

BATCH = 120  # people looked for at a time
log = get_logger("portalab.cards")
TYPE_ORDER = {"still": 0, "backdrop": 1}


def best(images: Sequence[CardImage]) -> tuple[str | None, str | None]:
    """The character's two images of one work, the card's and the borderless alternative's: stills, else
    backdrops, the best liked — never a poster (tagged with the whole cast, it shows the lead)."""
    shots = [i for i in images if i.image_type in TYPE_ORDER]
    ordered = sorted(shots, key=lambda i: (TYPE_ORDER[i.image_type], -i.votes, -i.aspect))
    art = ordered[0].image if ordered else None
    alt = next((i.image for i in ordered if i.image != art), None)
    return art, alt


class RoleArt:
    def __init__(
        self, database: Database, capabilities: CapabilityRegistry, *, clock: Clock | None = None
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.clock = clock

    async def run(self, batch: int = BATCH) -> int:
        """Look for the characters of the next people (the rarest cards first): how many cards got one."""
        providers = self.capabilities.system_providers(CARD_SOURCES)
        if not providers:
            return 0
        sources: Any = providers[0].provider
        rank = case(
            (Card.rarity == "legendary", 0), (Card.rarity == "epic", 1), (Card.rarity == "rare", 2), else_=3
        )
        async with self.database.session() as session:
            people = list(
                (
                    await session.execute(
                        select(Card.person_ref)
                        .join(CardSet, CardSet.key == Card.set_key)
                        .where(
                            Card.kind == "cast",
                            Card.retired.is_(False),
                            Card.role_checked_at.is_(None),
                            Card.person_ref.like("tmdb:%"),
                            CardSet.present.is_(True),
                            CardSet.tmdb.is_not(None),
                        )
                        .group_by(Card.person_ref)
                        .order_by(func.min(rank), func.max(Card.score).desc())
                        .limit(batch)
                    )
                ).scalars()
            )
        found = 0
        for person in [p for p in people if p]:
            try:
                images = await sources.role_images(person)
                if images is None:
                    break  # no provider can tell: nothing is marked, looked for again later
            except Exception:  # the provider does not answer: looked for again next time
                log.warning("characters' images not found", exc_info=True)
                continue
            found += await self._apply(person, images)
        return found

    async def _apply(self, person: str, images: Sequence[CardImage]) -> int:
        by_work: dict[str, list[CardImage]] = defaultdict(list)
        for image in images:
            by_work[image.work].append(image)
        now = utc_now(self.clock)
        given = 0
        async with self.database.unit_of_work() as uow:
            rows = (
                await uow.session.execute(
                    select(Card, CardSet.tmdb)
                    .join(CardSet, CardSet.key == Card.set_key)
                    .where(Card.person_ref == person, Card.kind == "cast", Card.role_checked_at.is_(None))
                )
            ).all()
            for card, tmdb in rows:
                card.role_art, card.role_alt = best(by_work.get(tmdb or "", []))
                card.role_checked_at = now
                given += 1 if card.role_art else 0
        return given
