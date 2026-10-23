"""Issue 229: the cards are made in advance from the works present (``media.card_sources``) — a set per film
or series: the work's card, then who made it (director, creator, writers, composer) and who plays in it (the
first names of its credits), numbered once and for all (a card keeps its number when its set is made again; a
new one takes the next). A work whose credits or artwork changed is made again (its fingerprint); a work gone
keeps its set, no longer present (owned copies stay). Rarities are ranked again whenever anything changed."""

import hashlib
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text, update

from portalab.capabilities.media_core import CARD_SOURCES, CardPerson, CardWork
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.cards.family import family_of
from portalab.modules.cards.models import Card, CardSet
from portalab.modules.cards.rarity import Ranked, card_score, rarities, work_fame

CAST = 10  # the first names of the credits made into cards
ANIMATION = {
    "animation",
    "animación",
    "animazione",
    "animatie",
    "zeichentrick",
}  # the genre, as providers name it
WRITERS = 2
ORDER = ("title", "director", "creator", "cast", "writer", "composer")
STOP = {
    "the", "a", "an", "of", "and", "in", "on", "to", "for",
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "l", "d",
    "par", "pour", "sur", "dans", "en", "au", "aux",
}  # fmt: skip


@dataclass(frozen=True, slots=True)
class Planned:
    ident: str
    kind: str
    person_ref: str | None
    name: str
    role: str | None
    flavor: str | None
    art: str | None
    alt_art: str | None
    billing: int


@dataclass
class SyncReport:
    works: int = 0
    made: int = 0
    unchanged: int = 0
    gone: int = 0
    cards: int = 0


def set_code(title: str) -> str:
    """Three letters, like a set's symbol: the initials of its first words — numbers and little words left
    out (« 120 battements par minute »: BMI), unless the title is only that (« 1917 »: 191)."""
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().upper()
    every = re.findall(r"[A-Z0-9]+", plain)
    words = [w for w in every if w.lower() not in STOP and not w.isdigit()] or every
    initials = "".join(w[0] for w in words[:3])
    if len(initials) < 3:
        initials = (initials + words[-1][1:])[:3] if words else "SET"  # the last word's next letters
    return initials[:3].ljust(3, "X")


def fingerprint(work: CardWork) -> str:
    data = {
        "title": work.title,
        "tagline": work.tagline,
        "poster": work.poster,
        "backdrops": list(work.backdrops)[:12],
        "people": [(p.ref, p.category, p.role, p.order, p.image) for p in work.people],
        "votes": work.vote_count // 50,  # a few more votes do not make it again
        "countries": list(work.countries)[:1],
        "tmdb": work.tmdb,
        "ids": sorted(work.ids.items()),
        "animated": any(g.strip().lower() in ANIMATION for g in work.genres),
        "genres": list(work.genres),
        "facts": sorted(work.facts.items()),
        # how the cards are made: v2 no image of the work on a person's, v3 the set's scene, v4 codes, v5 the
        # genre's colour and the work's figures, v6 its genres printed, v7 no gold body
        "v": 7,
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:64]


def plan(work: CardWork) -> list[Planned]:
    """The cards of a work, in their set's order."""
    arts = [a for a in [work.backdrop, *work.backdrops] if a]

    def alt(index: int) -> str | None:  # a borderless art per card
        return arts[index % len(arts)] if arts else None

    out = [
        Planned("title", "title", None, work.title, None, work.tagline, work.poster, alt(0), 0),
    ]
    seen: set[str] = set()

    def add(person: CardPerson, kind: str) -> None:
        ident = f"{kind}:{person.ref}"
        if ident in seen:
            return
        seen.add(ident)
        out.append(
            Planned(
                ident,
                kind,
                person.ref,
                person.name,
                person.role,
                None,
                person.image,
                None,  # never an image of the work: it shows someone else (their character's, once found)
                person.order,
            )
        )

    people = list(work.people)
    for kind in ("director", "creator"):
        for person in people:
            if person.category == kind:
                add(person, kind)
    for person in sorted((p for p in people if p.category == "cast"), key=lambda p: p.order)[:CAST]:
        add(person, "cast")
    for person in [p for p in people if p.category == "writer"][:WRITERS]:
        add(person, "writer")
    for person in [p for p in people if p.category == "composer"][:1]:
        add(person, "composer")
    return out


class CardForge:
    def __init__(
        self, database: Database, capabilities: CapabilityRegistry, *, clock: Clock | None = None
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.clock = clock

    def _sources(self) -> Any | None:
        providers = self.capabilities.system_providers(CARD_SOURCES)
        return providers[0].provider if providers else None

    async def sync(self) -> SyncReport:
        report = SyncReport()
        sources = self._sources()
        if sources is None:
            return report
        works: Sequence[CardWork] = await sources.works()
        report.works = len(works)
        now = utc_now(self.clock)
        changed = False
        async with self.database.unit_of_work() as uow:
            session = uow.session
            # one making at a time (the worker's job and an administrator's request)
            await session.execute(text("SELECT pg_advisory_xact_lock(hashtext('cards.sync'))"))
            known = {s.key: s for s in (await session.execute(select(CardSet))).scalars()}
            seen: set[str] = set()
            for work in works:
                key = str(work.object_id)
                seen.add(key)
                print_ = fingerprint(work)
                current = known.get(key)
                if current is not None and current.fingerprint == print_ and current.present:
                    report.unchanged += 1
                    continue
                await self._make(session, work, current, print_, now)
                report.made += 1
                changed = True
            gone = [key for key, s in known.items() if key not in seen and s.present]
            if gone:
                await session.execute(update(CardSet).where(CardSet.key.in_(gone)).values(present=False))
                report.gone = len(gone)
                changed = True
        if changed or not known:
            report.cards = await self.rank(works)
        return report

    async def _make(
        self, session: Any, work: CardWork, current: CardSet | None, print_: str, now: Any
    ) -> None:
        key = str(work.object_id)
        planned = plan(work)
        if current is None:
            current = CardSet(key=key, object_id=work.object_id)
            session.add(current)
        current.kind = work.kind
        current.name = work.title
        current.code = set_code(work.title)
        current.year = work.year
        current.country = (work.countries[0] if work.countries else None) or None
        current.poster = work.poster
        current.backdrop = work.backdrop or next(iter(work.backdrops), None)
        current.animated = any(g.strip().lower() in ANIMATION for g in work.genres)
        current.family = family_of(work.genres)
        current.facts = {
            **dict(work.facts),
            **({"rating": round(work.vote_average, 1)} if work.vote_average else {}),
            **({"votes": work.vote_count} if work.vote_count else {}),
            **({"genres": list(work.genres)[:3]} if work.genres else {}),
        }
        current.saga = (
            str(work.collection.get("name"))[:200]
            if work.collection and work.collection.get("name")
            else None
        )
        current.tmdb = work.tmdb
        current.ids = ",".join(f"{k}:{v}" for k, v in sorted(work.ids.items()))[:240] or None
        current.present = True
        current.fingerprint = print_
        current.generated_at = now
        await session.flush()
        cards = {
            c.ident: c for c in (await session.execute(select(Card).where(Card.set_key == key))).scalars()
        }
        number = max((c.number for c in cards.values()), default=0)
        wanted = {p.ident for p in planned}
        for item in planned:
            card = cards.get(item.ident)
            if card is None:
                number += 1
                card = Card(set_key=key, ident=item.ident, number=number, score=0.0, rarity="common")
                session.add(card)
            card.kind = item.kind
            card.person_ref = item.person_ref
            card.name = item.name[:200]
            card.role = item.role[:200] if item.role else None
            card.flavor = item.flavor[:300] if item.flavor else None
            card.art = item.art
            card.alt_art = item.alt_art
            card.billing = item.billing
            card.retired = False
            card.updated_at = now
        for ident, card in cards.items():
            if ident not in wanted:
                card.retired = True
                card.updated_at = now
        current.size = len(planned)

    async def rank(self, works: Sequence[CardWork] | None = None) -> int:
        """Every card's score and rarity, ranked again across the library (per country)."""
        sources = self._sources()
        if works is None:
            works = await sources.works() if sources is not None else []
        fame = {str(w.object_id): work_fame(w.vote_count, w.vote_average) for w in works}
        async with self.database.unit_of_work() as uow:
            session = uow.session
            rows = (
                await session.execute(
                    select(Card, CardSet.country)
                    .join(CardSet, CardSet.key == Card.set_key)
                    .where(Card.retired.is_(False), CardSet.present.is_(True))
                )
            ).all()
            appearances = Counter(card.person_ref for card, _ in rows if card.person_ref)
            ranked = []
            by_id: dict[object, Card] = {}
            for card, country in rows:
                score = card_score(
                    card.kind,
                    card.billing,
                    fame.get(card.set_key, 0.0),
                    appearances.get(card.person_ref or "", 0),
                )
                if card.score != score:
                    card.score = score
                by_id[card.id] = card
                ranked.append(Ranked(card.id, score, country))
            for card_id, rarity in rarities(ranked).items():
                card = by_id[card_id]
                if card.rarity != rarity:
                    card.rarity = rarity
        return len(rows)
