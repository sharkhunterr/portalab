"""Issue 229: what members see of the cards — their collection (how many of each set they own), a set's cards
(owned or still to find, each in the versions owned), a person's cards across the sets, and their packs."""

from collections import defaultdict
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Text, cast, func, or_, select

from portalab.core.db import Database
from portalab.modules.cards.editions import edition_of
from portalab.modules.cards.models import Card, CardSet, Copy, Pack

PAGE = 48


def card_out(card: Card, card_set: CardSet, owned: dict[str, int] | None = None) -> dict[str, Any]:
    return {
        "id": str(card.id),
        "set": card_set.key,
        "set_code": card_set.code,
        "set_name": card_set.name,
        "set_size": card_set.size,
        "set_kind": card_set.kind,
        "set_backdrop": card_set.backdrop,
        "set_poster": card_set.poster,
        "set_family": card_set.family,
        "set_edition": edition_of(card_set.year),
        "set_facts": card_set.facts or {},
        "set_animated": card_set.animated,
        "year": card_set.year,
        "number": card.number,
        "kind": card.kind,
        "person": card.person_ref,
        "name": card.name,
        "role": card.role,
        "flavor": card.flavor,
        "art": card.art,
        "alt_art": card.alt_art,
        "role_art": card.role_art,
        "role_alt": card.role_alt,
        "fan_art": card.fan_art,
        "focus": card.focus or {},
        "cutout": card.cutout or {},
        "rarity": card.rarity,
        "billing": card.billing,
        "retired": card.retired,
        "owned": owned or {},
    }


def _pack_look(
    card_set: CardSet | None, detail: dict[str, Any], art: str | None = None
) -> dict[str, Any] | None:
    if card_set is None:
        if not detail.get("product"):
            return None
        # a shop's booster: the works it draws among (all of them when unsaid)
        return {
            "kind": detail.get("kind"),
            "code": None,
            "year": None,
            "family": detail.get("family"),
            "edition": detail.get("edition"),
            "rarity": detail.get("rarity"),  # issue 255: the rarity it guarantees
            "poster": None,
            "backdrop": None,
            "logos": {},
            "season": None,
            "product": detail.get("product"),
        }
    return {
        "kind": card_set.kind,
        "code": card_set.code,
        "year": card_set.year,
        "family": card_set.family,
        "edition": edition_of(card_set.year),
        "poster": card_set.poster,
        "backdrop": card_set.backdrop,
        "logos": card_set.logos or {},
        "art": art,
        "season": detail.get("season"),
    }


class CardService:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def _owned(self, session: Any, user: UUID, card_ids: Sequence[UUID]) -> dict[UUID, dict[str, int]]:
        out: dict[UUID, dict[str, int]] = defaultdict(dict)
        if not card_ids:
            return out
        rows = (
            await session.execute(
                select(Copy.card_id, Copy.variant, func.count())
                .outerjoin(Pack, Pack.id == Copy.pack_id)
                # a card of an unopened pack is not seen yet
                .where(
                    Copy.user_id == user,
                    Copy.card_id.in_(card_ids),
                    or_(Pack.id.is_(None), Pack.opened_at.is_not(None)),
                )
                .group_by(Copy.card_id, Copy.variant)
            )
        ).all()
        for card_id, variant, count in rows:
            out[card_id][variant] = int(count)
        return out

    def _seen(self) -> Any:
        return or_(Pack.id.is_(None), Pack.opened_at.is_not(None))

    async def shows(self, art: str) -> bool:
        """Whether a card shows this image (the only ones the cards serve)."""
        async with self.database.session() as session:
            shown = or_(Card.role_art == art, cast(Card.cutout, Text).contains(f'"{art}"'))
            return bool(await session.scalar(select(Card.id).where(shown).limit(1)))

    async def summary(self, user: UUID) -> dict[str, Any]:
        async with self.database.session() as session:
            owned = (
                await session.execute(
                    select(
                        func.count(func.distinct(Copy.card_id)),
                        func.count(Copy.id),
                        func.count(func.distinct(Card.set_key)),
                    )
                    .join(Card, Card.id == Copy.card_id)
                    .outerjoin(Pack, Pack.id == Copy.pack_id)
                    .where(Copy.user_id == user, self._seen())
                )
            ).one()
            total = await session.scalar(
                select(func.count())
                .select_from(Card)
                .join(CardSet, CardSet.key == Card.set_key)
                .where(Card.retired.is_(False), CardSet.present.is_(True))
            )
            sets = await session.scalar(
                select(func.count()).select_from(CardSet).where(CardSet.present.is_(True))
            )
            unopened = await session.scalar(
                select(func.count()).select_from(Pack).where(Pack.user_id == user, Pack.opened_at.is_(None))
            )
        return {
            "unique": int(owned[0] or 0),
            "copies": int(owned[1] or 0),
            "sets_started": int(owned[2] or 0),
            "cards": int(total or 0),
            "sets": int(sets or 0),
            "unopened": int(unopened or 0),
        }

    async def sets(self, user: UUID, *, q: str = "", started: bool = False, page: int = 0) -> dict[str, Any]:
        owned = (
            select(Card.set_key.label("key"), func.count(func.distinct(Copy.card_id)).label("owned"))
            .join(Copy, Copy.card_id == Card.id)
            .outerjoin(Pack, Pack.id == Copy.pack_id)
            .where(Copy.user_id == user, self._seen())
            .group_by(Card.set_key)
            .subquery()
        )
        query = (
            select(CardSet, func.coalesce(owned.c.owned, 0))
            .outerjoin(owned, owned.c.key == CardSet.key)
            .where(CardSet.present.is_(True))
        )
        if q.strip():
            query = query.where(CardSet.name.ilike(f"%{q.strip()}%"))
        if started:
            query = query.where(owned.c.owned > 0)
        async with self.database.session() as session:
            total = await session.scalar(select(func.count()).select_from(query.subquery()))
            rows = (
                await session.execute(
                    query.order_by(func.coalesce(owned.c.owned, 0).desc(), CardSet.name)
                    .limit(PAGE)
                    .offset(page * PAGE)
                )
            ).all()
        return {
            "total": int(total or 0),
            "items": [
                {
                    "key": s.key,
                    "code": s.code,
                    "name": s.name,
                    "kind": s.kind,
                    "year": s.year,
                    "poster": s.poster,
                    "saga": s.saga,
                    "size": s.size,
                    "owned": int(n),
                }
                for s, n in rows
            ],
        }

    async def pool(
        self,
        user: UUID,
        *,
        q: str = "",
        rarity: str | None = None,
        kind: str | None = None,
        country: str | None = None,
        owned: bool = False,
        page: int = 0,
    ) -> dict[str, Any]:
        """Every card of the sets present (the pool), the rarest first, filtered — each with the versions I
        own."""
        query = (
            select(Card, CardSet)
            .join(CardSet, CardSet.key == Card.set_key)
            .where(Card.retired.is_(False), CardSet.present.is_(True))
        )
        if q.strip():
            like = f"%{q.strip()}%"
            query = query.where(or_(Card.name.ilike(like), CardSet.name.ilike(like), Card.role.ilike(like)))
        if rarity:
            query = query.where(Card.rarity == rarity)
        if kind:
            query = query.where(Card.kind == kind)
        if country:
            query = query.where(CardSet.country == country)
        if owned:
            mine = (
                select(Copy.card_id)
                .outerjoin(Pack, Pack.id == Copy.pack_id)
                .where(Copy.user_id == user, self._seen())
            )
            query = query.where(Card.id.in_(mine))
        async with self.database.session() as session:
            total = await session.scalar(select(func.count()).select_from(query.subquery()))
            rows = (
                await session.execute(
                    query.order_by(Card.score.desc(), CardSet.name, Card.number)
                    .limit(PAGE)
                    .offset(page * PAGE)
                )
            ).all()
            have = await self._owned(session, user, [c.id for c, _ in rows])
            countries = [
                c
                for (c,) in (
                    await session.execute(
                        select(CardSet.country)
                        .where(CardSet.present.is_(True), CardSet.country.is_not(None))
                        .group_by(CardSet.country)
                        .order_by(func.count().desc())
                        .limit(30)
                    )
                ).all()
            ]
        return {
            "total": int(total or 0),
            "countries": countries,
            "items": [card_out(c, s, have.get(c.id)) for c, s in rows],
        }

    async def set_detail(self, user: UUID, key: str) -> dict[str, Any] | None:
        async with self.database.session() as session:
            card_set = await session.get(CardSet, key)
            if card_set is None:
                return None
            cards = list(
                (
                    await session.execute(select(Card).where(Card.set_key == key).order_by(Card.number))
                ).scalars()
            )
            owned = await self._owned(session, user, [c.id for c in cards])
        shown = [c for c in cards if not c.retired or owned.get(c.id)]
        return {
            "key": card_set.key,
            "code": card_set.code,
            "name": card_set.name,
            "kind": card_set.kind,
            "year": card_set.year,
            "poster": card_set.poster,
            "backdrop": card_set.backdrop,
            "logos": card_set.logos or {},
            "saga": card_set.saga,
            "present": card_set.present,
            "size": card_set.size,
            "owned": sum(1 for c in shown if owned.get(c.id)),
            "cards": [card_out(c, card_set, owned.get(c.id)) for c in shown],
        }

    async def person(self, user: UUID, ref: str) -> dict[str, Any]:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Card, CardSet)
                    .join(CardSet, CardSet.key == Card.set_key)
                    .where(Card.person_ref == ref, or_(Card.retired.is_(False), CardSet.present.is_(True)))
                    .order_by(CardSet.year.desc().nulls_last(), CardSet.name)
                )
            ).all()
            owned = await self._owned(session, user, [c.id for c, _ in rows])
        cards = [card_out(c, s, owned.get(c.id)) for c, s in rows]
        return {
            "ref": ref,
            "name": cards[0]["name"] if cards else None,
            "art": next((c["art"] for c in cards if c["art"]), None),
            "size": len(cards),
            "owned": sum(1 for c in cards if c["owned"]),
            "cards": cards,
        }

    async def packs(self, user: UUID, *, unopened: bool = True, limit: int = 20) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            query = select(Pack).where(Pack.user_id == user)
            if unopened:
                query = query.where(Pack.opened_at.is_(None))
            packs = list((await session.execute(query.order_by(Pack.given_at.desc()).limit(limit))).scalars())
            if not packs:
                return []
            rows = (
                await session.execute(
                    select(Copy, Card, CardSet)
                    .join(Card, Card.id == Copy.card_id)
                    .join(CardSet, CardSet.key == Card.set_key)
                    .where(Copy.pack_id.in_([p.id for p in packs]))
                    .order_by(Copy.acquired_at, Copy.id)  # as drawn (its ids grow with time)
                )
            ).all()
            # issue 234: a content's booster wears its work's textless art (the art site's, its title card's)
            arts: dict[str, str | None] = {
                key: art
                for key, art in await session.execute(
                    select(Card.set_key, Card.fan_art).where(
                        Card.kind == "title", Card.set_key.in_([p.set_key for p in packs if p.set_key])
                    )
                )
            }
            sets = {
                s.key: s
                for s in (
                    await session.execute(
                        select(CardSet).where(CardSet.key.in_([p.set_key for p in packs if p.set_key]))
                    )
                ).scalars()
            }
            # issue 234: a card is new when this copy is the member's first of it (their ids follow time)
            firsts: dict[UUID, str] = {
                card_id: first
                for card_id, first in await session.execute(
                    select(Copy.card_id, func.min(cast(Copy.id, Text)))
                    .where(Copy.user_id == user, Copy.card_id.in_({c.card_id for c, _, _ in rows}))
                    .group_by(Copy.card_id)
                )
            }
        by_pack: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
        for copy, card, card_set in rows:
            by_pack[copy.pack_id].append(
                {
                    **card_out(card, card_set),
                    "variant": copy.variant,
                    "copy": str(copy.id),
                    "new": firsts.get(card.id) == str(copy.id),
                }
            )
        return [
            {
                "id": str(p.id),
                "source": p.source,
                "set": p.set_key,
                "set_name": sets[p.set_key].name if p.set_key in sets else None,
                # issue 234: its content's booster wears it — the work's art, its title drawn, the season
                "look": _pack_look(sets.get(p.set_key or ""), p.detail or {}, arts.get(p.set_key or "")),
                "given_at": p.given_at.isoformat(),
                "opened_at": p.opened_at.isoformat() if p.opened_at else None,
                # the cards stay hidden until it is opened
                "cards": by_pack.get(p.id, []) if p.opened_at else [],
                "count": len(by_pack.get(p.id, [])),
            }
            for p in packs
        ]

    async def pack(self, user: UUID, pack_id: UUID) -> dict[str, Any] | None:
        found = [p for p in await self.packs(user, unopened=False, limit=200) if p["id"] == str(pack_id)]
        return found[0] if found else None
