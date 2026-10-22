"""Issue 229 — the media cards: made in advance from the works present (a set per work, its cards numbered
once and for all, made again when the work changes), ranked by rarity per country; packs drawn when given and
revealed when opened; borderless versions only at the high rarities; a member's copies erased with them."""

import random
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.media_core import CARD_SOURCES, CardPerson, CardWork
from portalab.core.db import Database
from portalab.modules.cards.generator import CardForge, plan, set_code
from portalab.modules.cards.models import Card, CardSet, Copy
from portalab.modules.cards.packs import Packs, variant_for
from portalab.modules.cards.participant import CardsParticipant
from portalab.modules.cards.rarity import Ranked, rarities
from portalab.modules.cards.service import CardService
from tests.authz_fixtures import INSERT_USER

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 22, tzinfo=UTC)


def work(title: str, votes: int, country: str, cast: list[str], director: str = "Someone") -> CardWork:
    people = [CardPerson(f"tmdb:{director}", director, "director", "Director", 0, f"/{director[:3]}.jpg")]
    people += [CardPerson(f"tmdb:{name}", name, "cast", f"as {name}", i, None) for i, name in enumerate(cast)]
    return CardWork(
        object_id=uuid4(),
        kind="movie",
        title=title,
        year=2022,
        countries=[country],
        languages=["English"],
        vote_count=votes,
        vote_average=7.5,
        tagline="A tagline",
        poster="/poster.jpg",
        backdrop="/back.jpg",
        backdrops=["/b1.jpg", "/b2.jpg"],
        collection={"name": "A saga"},
        people=people,
        updated_at=NOW,
        available=True,
    )


class Sources:
    def __init__(self, works: list[CardWork]) -> None:
        self.items = works

    async def works(self, *, since: datetime | None = None) -> list[CardWork]:
        return self.items

    async def present(self) -> list[UUID]:
        return [w.object_id for w in self.items]

    async def work_of(self, object_id: UUID) -> UUID | None:
        return object_id if any(w.object_id == object_id for w in self.items) else None


def test_plan_and_codes() -> None:
    made = plan(work("Top Gun: Maverick", 11000, "US", ["Tom Cruise", "Miles Teller", "Tom Cruise"]))
    assert [(p.kind, p.name) for p in made] == [
        ("title", "Top Gun: Maverick"),
        ("director", "Someone"),
        ("cast", "Tom Cruise"),
        ("cast", "Miles Teller"),
    ]
    assert all(p.alt_art for p in made)  # a borderless art for every card
    assert set_code("Top Gun: Maverick") == "TGM"
    assert set_code("Le Voyage de Chihiro") == "VCH"
    assert set_code("Up") == "UPX"


def test_rarity_is_ranked_per_country() -> None:
    # a small French cohort ranked with the library, a big one on its own: each has its own legendaries
    cards = [Ranked(f"us{i}", float(i), "US") for i in range(400)]
    cards += [Ranked(f"fr{i}", float(i) / 100, "FR") for i in range(400)]
    ranks = rarities(cards)
    assert ranks["fr399"] == "legendary" and ranks["us399"] == "legendary"
    assert ranks["fr0"] == "common"
    counts = {
        r: sum(1 for k, v in ranks.items() if k.startswith("fr") and v == r) for r in set(ranks.values())
    }
    assert counts["legendary"] == 10 and counts["epic"] == 38


def test_borderless_only_at_high_rarities() -> None:
    rng = random.Random(7)  # noqa: S311 — deterministic test data
    commons = {variant_for("common", rng) for _ in range(2000)}
    legendaries = [variant_for("legendary", rng) for _ in range(2000)]
    assert commons <= {"normal", "foil"}
    assert 350 < sum(v.startswith("borderless") for v in legendaries) < 650


async def test_made_numbered_ranked_drawn_and_erased(database: Database) -> None:
    capabilities = new_registry()
    first = work("Top Gun: Maverick", 11000, "US", ["Tom Cruise", "Miles Teller"])
    second = work("OSS 117", 3000, "FR", ["Jean Dujardin"], director="Michel Hazanavicius")
    sources = Sources([first, second])
    capabilities.provide(CARD_SOURCES, sources, instance_ref="t", owner="test")
    forge = CardForge(database, capabilities)
    report = await forge.sync()
    assert (report.made, report.cards) == (2, 7)
    assert (await forge.sync()).made == 0  # nothing changed: nothing made again

    async with database.session() as session:
        top = await session.get(CardSet, str(first.object_id))
        assert top is not None and (top.code, top.size, top.saga) == ("TGM", 4, "A saga")
    # the credits change: a new card takes the next number, a card no longer credited is retired
    sources.items[0] = replace(
        first,
        people=[
            *first.people[:2],
            CardPerson("tmdb:Jennifer", "Jennifer Connelly", "cast", "Penny", 2, None),
        ],
    )
    assert (await forge.sync()).made == 1
    service = CardService(database)
    user = uuid4()
    async with database.unit_of_work() as uow:
        await uow.session.execute(INSERT_USER, {"id": user, "login": f"u{user.hex[:8]}"})
    detail = await service.set_detail(user, str(first.object_id))
    assert detail is not None
    assert [(c["number"], c["name"]) for c in detail["cards"]] == [
        (1, "Top Gun: Maverick"),
        (2, "Someone"),
        (3, "Tom Cruise"),
        (5, "Jennifer Connelly"),
    ]

    packs = Packs(database, capabilities, rng=random.Random(3))  # noqa: S311 — deterministic test data
    pack = await packs.give(user, "watched", str(first.object_id), "k1")
    assert pack is not None and await packs.give(user, "watched", str(first.object_id), "k1") is None
    unopened = await service.packs(user)
    assert unopened[0]["count"] == 3 and unopened[0]["cards"] == []  # hidden until opened
    assert (await service.summary(user))["unique"] == 0
    await packs.open(user, pack)
    opened = await service.pack(user, pack)
    assert opened is not None and len(opened["cards"]) == 3
    assert opened["cards"][0]["set"] == str(first.object_id)  # the first card: of the work watched
    summary = await service.summary(user)
    assert summary["copies"] == 3 and summary["unopened"] == 0
    person = await service.person(user, "tmdb:Tom Cruise")
    assert person["size"] == 1 and person["name"] == "Tom Cruise"

    participant = CardsParticipant(database)
    assert len(await participant.export(user)) == 3
    await participant.erase(user, "delete")
    async with database.session() as session:
        left: Any = (await session.execute(Copy.__table__.select().where(Copy.user_id == user))).all()
        assert left == []
        assert (await session.execute(Card.__table__.select())).all()  # the cards stay
