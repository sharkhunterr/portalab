"""Issue 229: packs of cards given to members — a work watched to the end gives a pack of three: one card of
that work, two of the whole library present. Its cards are drawn when it is given (by rarity, then a card of
that rarity), revealed when it is opened.

A copy's version is drawn with it, like a trading card game's: foil at any rarity; the borderless versions
(the full-art alternative: a work's scene over the whole card) for the works' cards only, mostly at the high
rarities — never a common, seldom a rare, often an epic or a legendary — and borderless foil rarer still."""

import random
import secrets
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.capabilities.media_core import CARD_SOURCES
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.cards.models import Card, CardSet, Copy, Pack

OWNER = "module:cards"
CONSUMER = "cards.watched_packs"
SIZE = 3
PER_DAY = 5  # packs a member may be given a day by watching
RARITY_WEIGHTS = {"common": 60, "rare": 28, "epic": 9, "legendary": 3}
TRIAL_SIZE = 6  # an administrator's trial pack: more cards, the special versions more often
TRIAL_FOIL = 0.4
TRIAL_BORDERLESS = 0.5
FOIL = 1 / 8
# the chance a copy is borderless (the full-art alternative), by the card's rarity
BORDERLESS = {"common": 0.0, "rare": 1 / 40, "epic": 1 / 10, "legendary": 1 / 4}


def variant_for(rarity: str, rng: random.Random, kind: str = "title") -> str:
    # the borderless alternative is a work's: its scene over the whole card (a person's card has none)
    borderless = kind == "title" and rng.random() < BORDERLESS.get(rarity, 0.0)
    foil = rng.random() < FOIL
    if borderless:
        return "borderless_foil" if foil else "borderless"
    return "foil" if foil else "normal"


class Packs:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self.rng = rng or secrets.SystemRandom()

    # --- drawing ------------------------------------------------------------------------------------------
    async def _draw(self, session: Any, set_key: str | None) -> Card | None:
        rarity = self.rng.choices(list(RARITY_WEIGHTS), weights=list(RARITY_WEIGHTS.values()), k=1)[0]
        base = (
            select(Card)
            .join(CardSet, CardSet.key == Card.set_key)
            .where(Card.retired.is_(False), CardSet.present.is_(True))
        )
        if set_key is not None:
            base = base.where(Card.set_key == set_key)
        for wanted in (rarity, None):  # that rarity, else any (a set may hold none of it)
            query = base.where(Card.rarity == wanted) if wanted else base
            found: Card | None = (
                await session.execute(query.order_by(func.random()).limit(1))
            ).scalar_one_or_none()
            if found is not None:
                return found
        return None

    async def give(self, user: UUID, source: str, set_key: str | None, key: str) -> UUID | None:
        """A pack for this member (once per ``key``): its cards drawn now, revealed when opened."""
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            pack_id = (
                await session.execute(
                    insert(Pack)
                    .values(
                        user_id=user,
                        source=source,
                        set_key=set_key,
                        idempotency_key=key[:200],
                        given_at=now,
                        detail={},
                    )
                    .on_conflict_do_nothing(index_elements=["idempotency_key"])
                    .returning(Pack.id)
                )
            ).scalar_one_or_none()
            if pack_id is None:
                return None  # given already
            for index in range(SIZE):
                card = await self._draw(session, set_key if index == 0 else None)
                if card is None:
                    continue
                session.add(
                    Copy(
                        user_id=user,
                        card_id=card.id,
                        variant=variant_for(card.rarity, self.rng, card.kind),
                        pack_id=pack_id,
                        acquired_at=now,
                    )
                )
        return pack_id

    # --- a trial pack (issue 229): to see the cards as they are drawn ------------------------------------
    async def trial(self, user: UUID, size: int = TRIAL_SIZE) -> UUID:
        """An administrator's trial pack: ``size`` cards drawn among the works whose characters were looked
        for (their images known), the special versions more often — every rendering seen in a few packs."""
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            looked = list(
                (
                    await session.execute(
                        select(Card.set_key).where(Card.character_checked_at.is_not(None)).distinct()
                    )
                ).scalars()
            )
            pack_id = (
                await session.execute(
                    insert(Pack)
                    .values(
                        user_id=user,
                        source="trial",
                        set_key=None,
                        idempotency_key=f"trial:{user}:{now.isoformat()}:{self.rng.random()}"[:200],
                        given_at=now,
                        detail={},
                    )
                    .returning(Pack.id)
                )
            ).scalar_one()
            for _ in range(size):
                card = await self._draw(session, self.rng.choice(looked) if looked else None)
                if card is None:
                    continue
                borderless = card.kind == "title" and self.rng.random() < TRIAL_BORDERLESS
                foil = self.rng.random() < TRIAL_FOIL
                variant = "borderless" if borderless else "normal"
                variant = f"{variant}_foil" if foil and borderless else ("foil" if foil else variant)
                session.add(
                    Copy(user_id=user, card_id=card.id, variant=variant, pack_id=pack_id, acquired_at=now)
                )
        return pack_id

    # --- a work watched to the end ------------------------------------------------------------------------
    def consumer(self) -> Consumer:
        return Consumer(
            CONSUMER, frozenset({"media.playback_finished"}), self.handle, OWNER, replay_safe=True
        )

    async def handle(self, envelope: Envelope, ctx: ConsumerContext) -> None:
        raw = envelope.payload.get("object")
        if ctx.replay or envelope.subject_type != "user" or not envelope.subject_id or not raw:
            return
        providers = self.capabilities.system_providers(CARD_SOURCES)
        if not providers:
            return
        work = await providers[0].provider.work_of(UUID(str(raw)))
        if work is None:
            return
        user = UUID(envelope.subject_id)
        day = envelope.occurred_at.date().isoformat()
        async with self.database.session() as session:
            known = await session.get(CardSet, str(work))
            given = await session.scalar(
                select(func.count())
                .select_from(Pack)
                .where(Pack.user_id == user, Pack.given_at >= utc_now(self.clock) - timedelta(days=1))
            )
        if known is None or int(given or 0) >= PER_DAY:
            return
        await self.give(user, "watched", str(work), f"watched:{user}:{work}:{day}")

    # --- opening ------------------------------------------------------------------------------------------
    async def open(self, user: UUID, pack_id: UUID) -> datetime | None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            pack = await uow.session.get(Pack, pack_id, with_for_update=True)
            if pack is None or pack.user_id != user:
                return None
            if pack.opened_at is None:
                pack.opened_at = now
            return pack.opened_at

    async def unopened(self, user: UUID) -> Sequence[Pack]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(Pack)
                        .where(Pack.user_id == user, Pack.opened_at.is_(None))
                        .order_by(Pack.given_at)
                    )
                ).scalars()
            )
