"""Issue 229: packs of cards given to members — a content's booster holds three cards of its work, never twice
the same while others are left. Issue 234: what gives one is the administrators' — a reward rule (« a film
watched to the end », « a season finished ») gives its event's content's boosters, once per member and
content. Its cards are drawn when it is given (by rarity, then a card of that rarity), revealed when opened.

A copy's version is drawn with it, like a trading card game's: foil at any rarity; the borderless versions
(the full-art alternative: a work's scene over the whole card) for the works' cards only, mostly at the high
rarities — never a common, seldom a rare, often an epic or a legendary — and borderless foil rarer still.
Issue 233: any card of a work with a year of release may come in its edition's version (its edition's frame),
the more often the rarer, foil or not. Issue 255: a legendary of such a work, now and then, in its edition's
HD version — a character without the frame around it over the edition's animated backdrop, a work borderless
and animated — always foil."""

import random
import re
import secrets
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.marketplace import ActivationResult, OwnershipView
from portalab.capabilities.media_core import CARD_SOURCES
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.cards.editions import EDITIONS, edition_of
from portalab.modules.cards.events import PACK_OPENED, SET_COMPLETED
from portalab.modules.cards.family import FAMILIES, GENRES
from portalab.modules.cards.models import Card, CardSet, Copy, Pack

WITHOUT_CARDS = ("progression", "none")  # issue 243: the welcome's answers without the cards

OWNER = "module:cards"
SIZE = 3
PER_DAY = 10  # contents' boosters a member may be given a day
RARITY_WEIGHTS = {"common": 60, "rare": 28, "epic": 9, "legendary": 3}
TRIAL_SIZE = 6  # an administrator's trial pack: more cards, the special versions more often
TRIAL_FOIL = 0.4
TRIAL_BORDERLESS = 0.5
TRIAL_SHOWCASE = 0.5
TRIAL_GENRE = 0.5
FOIL = 1 / 8
# the chance a copy is borderless (the full-art alternative), by the card's rarity
BORDERLESS = {"common": 0.0, "rare": 1 / 40, "epic": 1 / 10, "legendary": 1 / 4}
# the chance a copy is in its edition's version (issue 233), by the card's rarity
SHOWCASE = {"common": 1 / 30, "rare": 1 / 15, "epic": 1 / 8, "legendary": 1 / 5}
# issue 295: the chance a copy is in its genre's version (its genre's frame), by the card's rarity — every
# card has a genre; drawn when it is neither borderless nor in its edition's
GENRE = {"common": 1 / 30, "rare": 1 / 15, "epic": 1 / 8, "legendary": 1 / 5}
# issue 296: a booster's own frames — its genre's or its edition's version this many times more often in
# it (at most FAVOURED_AT_MOST), and its signature frame on this share of its cards (a rarity booster's: on
# the card it guarantees only)
FAVOUR = 3
FAVOURED_AT_MOST = 0.6
SIGNATURE = 1 / 4
SIGNATURE_LOOK = re.compile(r"^[a-z0-9-]{1,32}$")
# issue 255: the chance a copy is in its edition's HD version — a legendary's only
HD = {"legendary": 1 / 6}
TRIAL_HD = 0.5


# issue 234: what a shop's booster may draw among — the works' genre, edition, kind (all of them when unsaid)
WORK_KINDS = ("movie", "series")


def _among(among: Mapping[str, Any]) -> list[Any]:
    out: list[Any] = []
    family = among.get("family")
    if family in FAMILIES:
        out.append(CardSet.family == family)
    genre = among.get("genre")
    if genre in GENRES:
        out.append(CardSet.genre == genre)
    kind = among.get("kind")
    if kind in WORK_KINDS:
        out.append(CardSet.kind == kind)
    edition = among.get("edition")
    first = None
    for key, last in EDITIONS:
        if key == edition:
            out.append(CardSet.year.is_not(None))
            if first is not None:
                out.append(CardSet.year > first)
            if last is not None:
                out.append(CardSet.year <= last)
            break
        first = last
    return out


BOOSTER_FIELDS = ("family", "genre", "edition", "kind", "cards", "rarity", "signature")
# issue 255: a booster that guarantees a card of this rarity (one of its cards drawn at it)
GUARANTEES = ("rare", "epic", "legendary")
CARD_BOOSTER = "card_booster"


def booster_of(payload: Mapping[str, Any]) -> dict[str, Any]:
    """A shop's booster's own: what it draws among, how many cards (3 to 10) and the rarity it guarantees."""
    out: dict[str, Any] = {k: payload[k] for k in ("family", "edition", "kind") if payload.get(k)}
    # issue 296: the works of a main genre; the signature frame its cards may come in
    if payload.get("genre") in GENRES:
        out["genre"] = payload["genre"]
    if isinstance(payload.get("signature"), str) and SIGNATURE_LOOK.match(payload["signature"]):
        out["signature"] = payload["signature"]
    if payload.get("rarity") in GUARANTEES:
        out["rarity"] = payload["rarity"]
    try:
        out["cards"] = max(3, min(10, int(payload.get("cards") or SIZE)))
    except (TypeError, ValueError):
        out["cards"] = SIZE
    return out


def _favoured(chance: float, favoured: bool) -> float:
    return min(FAVOURED_AT_MOST, chance * FAVOUR) if favoured else chance


def variant_for(
    rarity: str,
    rng: random.Random,
    kind: str = "title",
    edition: str | None = None,
    favour: str | None = None,  # issue 296: "genre" or "showcase" — the version its booster favours
) -> str:
    if edition is not None and rng.random() < HD.get(rarity, 0.0):
        return "hd"  # issue 255: foil already, its frame its edition's
    # the borderless alternative is a work's: its scene over the whole card (a person's card has none)
    borderless = kind == "title" and rng.random() < BORDERLESS.get(rarity, 0.0)
    # its edition's version: a work released some year (its edition known)
    showcase = (
        not borderless
        and edition is not None
        and rng.random() < _favoured(SHOWCASE.get(rarity, 0.0), favour == "showcase")
    )
    # issue 295: its genre's version
    genre = (
        not borderless
        and not showcase
        and rng.random() < _favoured(GENRE.get(rarity, 0.0), favour == "genre")
    )
    foil = rng.random() < FOIL
    base = "borderless" if borderless else "showcase" if showcase else "genre" if genre else None
    if base:
        return f"{base}_foil" if foil else base
    return "foil" if foil else "normal"


class Packs:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
        rng: random.Random | None = None,
        events: EventPublisher | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self.events = events
        self.rng = rng or secrets.SystemRandom()

    # --- drawing ------------------------------------------------------------------------------------------
    async def _draw(
        self,
        session: Any,
        set_key: str | None,
        among: Mapping[str, Any] | None = None,
        drawn: Sequence[UUID] = (),
        rarity: str | None = None,  # issue 255: the rarity a booster guarantees, else drawn by the odds
    ) -> Card | None:
        rarity = (
            rarity or self.rng.choices(list(RARITY_WEIGHTS), weights=list(RARITY_WEIGHTS.values()), k=1)[0]
        )
        base = (
            select(Card)
            .join(CardSet, CardSet.key == Card.set_key)
            .where(Card.retired.is_(False), CardSet.present.is_(True))
        )
        if set_key is not None:
            base = base.where(Card.set_key == set_key)
        for condition in _among(among or {}):
            base = base.where(condition)
        # never twice the same card in a pack while others are left (a small set: again, then)
        fresh = base.where(Card.id.not_in(drawn)) if drawn else base
        for wanted, pool in ((rarity, fresh), (None, fresh), (None, base)):  # that rarity, else any
            query = pool.where(Card.rarity == wanted) if wanted else pool
            found: Card | None = (
                await session.execute(query.order_by(func.random()).limit(1))
            ).scalar_one_or_none()
            if found is not None:
                return found
        return None

    async def drawable(self, among: Mapping[str, Any]) -> bool:
        """Issue 234: whether a shop's booster has cards to draw among the works it names — issue 255: one of
        the rarity it guarantees among them."""
        query = (
            select(Card.id)
            .join(CardSet, CardSet.key == Card.set_key)
            .where(Card.retired.is_(False), CardSet.present.is_(True), *_among(among))
            .limit(1)
        )
        if among.get("rarity") in GUARANTEES:
            query = query.where(Card.rarity == among["rarity"])
        async with self.database.session() as session:
            return (await session.execute(query)).first() is not None

    async def give(
        self,
        user: UUID,
        source: str,
        set_key: str | None,
        key: str,
        detail: dict[str, Any] | None = None,
        among: Mapping[str, Any] | None = None,
        size: int = SIZE,
        guarantee: str | None = None,
    ) -> UUID | None:
        """A pack for this member (once per ``key``): its cards drawn now, revealed when opened — all of
        ``set_key`` (a content's) or ``among`` the works it names (issue 234: a shop's booster)."""
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
                        detail=detail or {},
                    )
                    .on_conflict_do_nothing(index_elements=["idempotency_key"])
                    .returning(Pack.id)
                )
            ).scalar_one_or_none()
            if pack_id is None:
                return None  # given already
            drawn: list[UUID] = []
            booster = among or {}
            # issue 296: the version its booster favours — a genre booster its genre's, an era's its edition's
            favour = "genre" if booster.get("genre") else "showcase" if booster.get("edition") else None
            for index in range(size):
                # issue 234: a content's booster holds its work's cards only; issue 255: its first card drawn
                # at the rarity it guarantees, before any other could take the only one there is
                card = await self._draw(session, set_key, among, drawn, guarantee if index == 0 else None)
                if card is None:
                    continue
                drawn.append(card.id)
                card_set = await session.get(CardSet, card.set_key)
                edition = edition_of(card_set.year if card_set else None)
                session.add(
                    Copy(
                        user_id=user,
                        card_id=card.id,
                        variant=self._signed(
                            variant_for(card.rarity, self.rng, card.kind, edition, favour),
                            booster.get("signature"),
                            index == 0 or not guarantee,
                        ),
                        pack_id=pack_id,
                        acquired_at=now,
                    )
                )
        return pack_id

    def _signed(self, variant: str, signature: str | None, may: bool) -> str:
        """Issue 296: a booster's signature frame — on a card in its base frame (foil or not), never over an
        edition's, a genre's, a borderless or an HD version; a rarity booster's on the card it guarantees."""
        if (
            signature is None
            or not may
            or variant not in ("normal", "foil")
            or self.rng.random() >= SIGNATURE
        ):
            return variant
        return f"signature{'_foil' if variant == 'foil' else ''}:{signature}"

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
                card_set = await session.get(CardSet, card.set_key)
                edition = edition_of(card_set.year if card_set else None)
                if edition is not None and card.rarity in HD and self.rng.random() < TRIAL_HD:
                    session.add(
                        Copy(user_id=user, card_id=card.id, variant="hd", pack_id=pack_id, acquired_at=now)
                    )
                    continue
                borderless = card.kind == "title" and self.rng.random() < TRIAL_BORDERLESS
                showcase = not borderless and edition is not None and self.rng.random() < TRIAL_SHOWCASE
                genre = not borderless and not showcase and self.rng.random() < TRIAL_GENRE
                foil = self.rng.random() < TRIAL_FOIL
                base = "borderless" if borderless else "showcase" if showcase else "genre" if genre else None
                variant = (f"{base}_foil" if foil else base) if base else ("foil" if foil else "normal")
                session.add(
                    Copy(user_id=user, card_id=card.id, variant=variant, pack_id=pack_id, acquired_at=now)
                )
        return pack_id

    # --- a content's boosters (issue 234): given by a reward rule ---------------------------------------
    async def collects(self, user: UUID) -> bool:
        """Issue 243: whether the member collects the cards — not when they answered the welcome's « do you
        want to play? » without the cards (or not at all); the other boosters are not concerned."""
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if not providers:
                return True
            play = (await providers[0].provider.get("shell.onboarding.play", user_id=user)).value
        except Exception:
            return True
        return play not in WITHOUT_CARDS

    async def give_content(self, user: UUID, object_id: UUID, count: int, reason: str) -> int:
        """``count`` boosters of this content (a film, a season: its work's cards) — once per member and
        content; none for a content without cards, nor past the day's share, nor to a member who does not
        collect the cards."""
        providers = self.capabilities.system_providers(CARD_SOURCES)
        if not providers or count < 1 or not await self.collects(user):
            return 0
        work = await providers[0].provider.work_of(object_id)
        if work is None:
            return 0
        async with self.database.session() as session:
            known = await session.get(CardSet, str(work))
            given = await session.scalar(
                select(func.count())
                .select_from(Pack)
                .where(
                    Pack.user_id == user,
                    Pack.source == "content",  # a trial or a bought booster is not a reward
                    Pack.given_at >= utc_now(self.clock) - timedelta(days=1),
                )
            )
        if known is None or not known.present or int(given or 0) >= PER_DAY:
            return 0
        season = await providers[0].provider.season_of(object_id)
        detail: dict[str, Any] = {"object": str(object_id), "reason": reason[:200]}
        if season is not None:
            detail["season"] = season  # its booster says which
        out = 0
        for index in range(min(count, 3)):
            key = f"content:{user}:{object_id}:{index}"
            if await self.give(user, "content", str(work), key, detail) is not None:
                out += 1
        return out

    # --- opening ------------------------------------------------------------------------------------------
    async def open(self, user: UUID, pack_id: UUID) -> datetime | None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            pack = await uow.session.get(Pack, pack_id, with_for_update=True)
            if pack is None or pack.user_id != user:
                return None
            if pack.opened_at is None:
                pack.opened_at = now
                await uow.session.flush()
                await self._opened(uow.session, user, pack, now)
            return pack.opened_at

    async def _opened(self, session: Any, user: UUID, pack: Pack, now: datetime) -> None:
        """Issue 234: what the achievements count — the booster opened, and each collection it completed."""
        if self.events is None:
            return
        drawn = (
            await session.execute(
                select(Card.set_key, Card.rarity, Copy.variant)
                .join(Copy, Copy.card_id == Card.id)
                .where(Copy.pack_id == pack.id)
            )
        ).all()
        subject = SubjectRef("user", str(user))
        rank = list(RARITY_WEIGHTS)
        await self.events.publish(
            session,
            PACK_OPENED,
            {
                "pack": str(pack.id),
                "source": pack.source,
                "cards": len(drawn),
                "best": max((r for _, r, _ in drawn), key=rank.index, default="common"),
                "legendary": sum(1 for _, r, _ in drawn if r == "legendary"),
                "foil": sum(1 for _, _, v in drawn if v == "foil" or v.split(":")[0].endswith("_foil")),
            },
            occurred_at=now,
            subject=subject,
            source="cards",
            dedup_key=f"{PACK_OPENED}:{pack.id}",
        )
        for set_key in sorted({s for s, _, _ in drawn}):
            missing = await session.scalar(
                select(func.count())
                .select_from(Card)
                .where(
                    Card.set_key == set_key,
                    Card.retired.is_(False),
                    ~Card.id.in_(
                        select(Copy.card_id)
                        .outerjoin(Pack, Pack.id == Copy.pack_id)
                        .where(Copy.user_id == user, or_(Pack.id.is_(None), Pack.opened_at.is_not(None)))
                    ),
                )
            )
            card_set = await session.get(CardSet, set_key)
            if missing or card_set is None:
                continue
            await self.events.publish(
                session,
                SET_COMPLETED,
                {
                    "set": set_key,
                    "object": str(card_set.object_id),
                    "kind": card_set.kind,
                    "size": card_set.size,
                },
                occurred_at=now,
                subject=subject,
                source="cards",
                dedup_key=f"{SET_COMPLETED}:{set_key}:{user}",
            )

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


class ContentBoosters:
    """Issue 234: the ``media.content_boosters`` capability — a reward rule's content boosters, the cards'."""

    def __init__(self, packs: Packs) -> None:
        self.packs = packs

    async def give(self, user: UUID, object_id: UUID, count: int, reason: str) -> int:
        return await self.packs.give_content(user, object_id, count, reason)


class CardBoosterHandler:
    """Issue 234: ``card_booster`` — a shop's booster of cards (``payload``: ``family``, ``edition``, ``kind``
    it draws among, how many ``cards``), sealed in the member's inventory when bought or offered; opened
    there. Consumed, not refundable."""

    def __init__(self, packs: Packs) -> None:
        self.packs = packs

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        booster = booster_of(ownership.payload)
        if not await self.packs.drawable(booster):
            return ActivationResult("incompatible", "no card among those works")
        # once per ownership: activated again, it is sealed already
        await self.packs.give(
            ownership.user_id,
            "shop",
            None,
            f"shop:{ownership.id}",
            {**booster, "product": ownership.product_key},
            among=booster,
            size=booster["cards"],
            guarantee=booster.get("rarity"),
        )
        return ActivationResult("active")

    async def deactivate(self, ownership: OwnershipView) -> None:
        return None
