"""Issue 229 — the media cards: made in advance from the works present (a set per work, its cards numbered
once and for all, made again when the work changes), ranked by rarity per country; packs drawn when given and
revealed when opened; borderless versions only at the high rarities; a member's copies erased with them."""

import random
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.marketplace import OwnershipView
from portalab.capabilities.media import ARTWORK, Artwork
from portalab.capabilities.media_core import CARD_SOURCES, CardImage, CardPerson, CardWork
from portalab.core.db import Database
from portalab.modules.cards.artwork import FanArt
from portalab.modules.cards.generator import CardForge, plan, set_code
from portalab.modules.cards.models import VARIANTS, Card, CardSet, Copy
from portalab.modules.cards.packs import CardBoosterHandler, ContentBoosters, Packs, booster_of, variant_for
from portalab.modules.cards.participant import CardsParticipant
from portalab.modules.cards.rarity import Ranked, rarities
from portalab.modules.cards.roles import RoleArt, best
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
        tmdb=str(abs(hash(title)) % 100000),
    )


class Sources:
    def __init__(self, works: list[CardWork]) -> None:
        self.items = works
        self.asked: list[str] = []

    async def works(self, *, since: datetime | None = None) -> list[CardWork]:
        return self.items

    async def present(self) -> list[UUID]:
        return [w.object_id for w in self.items]

    async def work_of(self, object_id: UUID) -> UUID | None:
        return object_id if any(w.object_id == object_id for w in self.items) else None

    async def season_of(self, object_id: UUID) -> int | None:
        return None

    async def image(self, ref: str, size: str) -> bytes:
        return b"face:cruise"  # a portrait (the faces' fake reads it)

    async def role_images(self, person_ref: str) -> list[CardImage]:
        self.asked.append(person_ref)
        if person_ref != "tmdb:Tom Cruise":
            return []
        work = self.items[0].tmdb or ""
        return [
            CardImage(work, "/poster.jpg", "poster", 0.67, 9.0),
            CardImage(work, "/still-b.jpg", "still", 1.78, 4.0),
            CardImage(work, "/still-a.jpg", "still", 1.78, 6.0),
            CardImage("other", "/elsewhere.jpg", "still", 1.78, 9.0),  # another work of theirs
        ]

    async def frames(self, object_id: UUID, at: list[float]) -> list[bytes] | None:
        return None  # no media server can show the film


def test_plan_and_codes() -> None:
    made = plan(work("Top Gun: Maverick", 11000, "US", ["Tom Cruise", "Miles Teller", "Tom Cruise"]))
    assert [(p.kind, p.name) for p in made] == [
        ("title", "Top Gun: Maverick"),
        ("director", "Someone"),
        ("cast", "Tom Cruise"),
        ("cast", "Miles Teller"),
    ]
    # the work's card has its borderless art; a person's never an image of the work (it shows someone else)
    assert made[0].alt_art and all(p.alt_art is None for p in made[1:])
    assert set_code("Top Gun: Maverick") == "TGM"
    assert set_code("Le Voyage de Chihiro") == "VCH"
    assert set_code("Up") == "UPX"
    assert set_code("120 battements par minute") == "BMI"  # numbers and little words left out
    assert set_code("13 Hours") == "HOU"
    assert set_code("1917") == "191"  # only a number: its digits


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
    # issue 295: besides, every card may come in its genre's version
    assert commons <= {"normal", "foil", "genre", "genre_foil"}
    # the borderless alternative is a work's only: never a person's card
    people = [variant_for("legendary", rng, "cast") for _ in range(2000)]
    assert not any(v.startswith("borderless") for v in people)
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
    # every card of the work watched, never twice the same
    assert {c["set"] for c in opened["cards"]} == {str(first.object_id)}
    assert len({c["id"] for c in opened["cards"]}) == 3
    assert opened["cards"][0]["new"] is True  # the member's first copy of it
    summary = await service.summary(user)
    assert summary["copies"] == 3 and summary["unopened"] == 0
    pool = await service.pool(user, rarity=None, kind="cast")
    assert pool["total"] == 3 and pool["countries"] == ["US", "FR"]
    assert (await service.pool(user, q="dujardin"))["items"][0]["name"] == "Jean Dujardin"
    person = await service.person(user, "tmdb:Tom Cruise")
    assert person["size"] == 1 and person["name"] == "Tom Cruise"

    participant = CardsParticipant(database)
    assert len(await participant.export(user)) == 3
    await participant.erase(user, "delete")
    async with database.session() as session:
        left: Any = (await session.execute(Copy.__table__.select().where(Copy.user_id == user))).all()
        assert left == []
        assert (await session.execute(Card.__table__.select())).all()  # the cards stay


async def test_an_actor_shows_their_character(database: Database) -> None:
    capabilities = new_registry()
    film = work("Top Gun: Maverick", 11000, "US", ["Tom Cruise", "Miles Teller"])
    sources = Sources([film])
    capabilities.provide(CARD_SOURCES, sources, instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    roles = RoleArt(database, capabilities)
    assert await roles.run() == 1  # Tom Cruise's character found, Miles Teller has none
    assert sorted(sources.asked) == ["tmdb:Miles Teller", "tmdb:Tom Cruise"]
    async with database.session() as session:
        cruise = (
            await session.execute(Card.__table__.select().where(Card.person_ref == "tmdb:Tom Cruise"))
        ).one()
    assert (cruise.role_art, cruise.role_alt) == ("/still-a.jpg", "/still-b.jpg")  # stills first, liked first
    # a poster shows the lead, whoever it is tagged with: never an actor's art
    assert best([CardImage("w", "/poster.jpg", "poster", 0.67, 9.0)]) == (None, None)
    assert await roles.run() == 0 and len(sources.asked) == 2  # kept: never looked for again


class Art:
    def __init__(self) -> None:
        self.asked: list[tuple[str, dict[str, str]]] = []

    async def artwork(self, kind: str, ids: Any) -> list[Artwork]:
        self.asked.append((kind, dict(ids)))
        return [
            Artwork("background", "/fanart/movies/1/moviebackground/en.jpg", "en", 50),  # text on it
            Artwork("thumb", "/fanart/movies/1/moviethumb/t.jpg", None, 90),
            Artwork("background", "/fanart/movies/1/moviebackground/a.jpg", None, 3),
            Artwork("background", "/fanart/movies/1/moviebackground/b.jpg", None, 8),
            Artwork("poster", "/fanart/movies/1/movieposter/titled.jpg", "en", 99),  # its title on it
        ]

    async def fetch_artwork(self, ref: str, preview: bool = False) -> bytes:
        return b""


async def test_a_works_borderless_art_from_an_art_site(database: Database) -> None:
    capabilities = new_registry()
    film = work("Top Gun: Maverick", 11000, "US", ["Tom Cruise"])
    film = replace(film, ids={"tmdb": "361743", "imdb": "tt1745960"})
    capabilities.provide(CARD_SOURCES, Sources([film]), instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    fan = FanArt(database, capabilities)
    assert await fan.run() == 0  # no art site connected: nothing marked
    art = Art()
    capabilities.provide(ARTWORK, art, instance_ref="fanart", owner="test")
    assert await fan.run() == 1
    assert art.asked == [("movie", {"imdb": "tt1745960", "tmdb": "361743"})]
    async with database.session() as session:
        title = (await session.execute(Card.__table__.select().where(Card.kind == "title"))).one()
    assert title.fan_art == "/fanart/movies/1/moviebackground/b.jpg"  # textless background, the best liked
    assert await fan.run() == 0 and len(art.asked) == 1  # kept: never asked again


def test_a_characters_image_is_scored() -> None:
    from portalab.modules.cards.faces import Candidate, score
    from portalab.modules.cards.search import query_for

    assert (
        query_for("Tom Cruise", "Capt. Pete 'Maverick' Mitchell", "Top Gun : Maverick")
        == "Tom Cruise Pete Maverick Mitchell Top Gun : Maverick"
    )
    film, role = "Interstellar", "Joseph Cooper"

    def kept(
        title: str, similarity: float = 0.7, size: tuple[int, int] = (1280, 720), engine: str = "bing images"
    ):
        return score(Candidate("u", title, engine, similarity, *size), role, film)

    assert kept("McConaughey as Cooper in Interstellar") > kept(
        "Interstellar wallpaper"
    )  # the character named
    assert kept("McConaughey as Cooper", similarity=0.3) is None  # not his face
    assert kept("McConaughey at the Interstellar premiere") is None  # an event
    assert kept("McConaughey smiling") is None  # nothing says it is this film
    assert kept("Cooper", size=(300, 200)) is None  # too small
    assert kept("Cooper", engine="wikicommons.images") is None


class Matcher:
    """Faces as their bytes say: ``face:<who>``; the same who, the same person."""

    async def ready(self) -> bool:
        return True

    def look(self, data: bytes) -> Any:
        from portalab.modules.cards.faces import Face, Looked

        text = data.decode()
        who = [part.removeprefix("face:") for part in text.split() if part.startswith("face:")]
        return Looked(tuple(Face(w, 0.05) for w in who), 1280, 720)

    def similarity(self, a: Any, b: Any) -> float:
        return 0.9 if a.signature == b.signature else 0.1


class Blobs:
    def __init__(self) -> None:
        self.kept: dict[str, bytes] = {}

    async def put(self, namespace: str, data: bytes, *, content_type: str) -> Any:
        from portalab.core.blobstore import StoredBlob

        key = f"{namespace}/{len(self.kept):064d}"
        self.kept[key] = data
        return StoredBlob(key, len(data), content_type)


class Web:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def images(self, query: str, limit: int = 30) -> list[Any]:
        from portalab.capabilities.media import ImageHit

        self.queries.append(query)
        return [
            ImageHit(
                "https://a/premiere.jpg", "Tom Cruise at the premiere of Top Gun: Maverick", 1280, 720, "bing"
            ),
            ImageHit("https://a/other.jpg", "Miles Teller in Top Gun: Maverick", 1280, 720, "bing"),
            ImageHit("https://a/him.jpg", "Tom Cruise as Maverick in Top Gun: Maverick", 1280, 720, "bing"),
            # a montage of him then and now, its page saying nothing of it: only his face twice betrays it
            ImageHit(
                "https://a/twice.jpg",
                "Tom Cruise Maverick in Top Gun: Maverick, 1986 and 2022",
                1280,
                720,
                "x",
            ),
        ]

    async def fetch(self, url: str) -> bytes:
        return {
            "https://a/premiere.jpg": b"face:cruise",
            "https://a/other.jpg": b"face:teller",
            "https://a/twice.jpg": b"face:cruise face:cruise",  # a montage: him twice
            "https://a/him.jpg": b"face:cruise jet",
        }[url]


async def test_an_actors_character_found_on_the_web(database: Database) -> None:
    from portalab.capabilities.media import IMAGE_SEARCH
    from portalab.modules.cards.search import RoleSearch

    capabilities = new_registry()
    film = work("Top Gun: Maverick", 11000, "US", ["Tom Cruise"])
    sources = Sources([film])

    capabilities.provide(CARD_SOURCES, sources, instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    async with database.unit_of_work() as uow:  # TMDB was asked and had nothing; his portrait is known
        await uow.session.execute(
            Card.__table__.update().where(Card.kind == "cast").values(role_checked_at=NOW, art="/cruise.jpg")
        )
    web, blobs = Web(), Blobs()
    search = RoleSearch(database, capabilities, Matcher(), blobs)  # type: ignore[arg-type]
    assert await search.run() == 0  # no search connected: nothing marked
    capabilities.provide(IMAGE_SEARCH, web, instance_ref="searxng", owner="test")
    assert await search.run() == 1
    assert web.queries == ["Tom Cruise as Tom Cruise Top Gun: Maverick"]
    assert list(blobs.kept.values()) == [b"face:cruise jet"]  # his face, the film named, not the premiere
    async with database.session() as session:
        cruise = (await session.execute(Card.__table__.select().where(Card.kind == "cast"))).one()
    assert cruise.role_art == f"blob:{next(iter(blobs.kept))}"
    assert await search.run() == 0 and len(web.queries) == 1  # kept: never searched again


def test_a_drawn_character_is_found_by_its_name() -> None:
    from portalab.modules.cards.faces import Candidate, score
    from portalab.modules.cards.search import query_for

    assert query_for(None, "Woody (voice)", "Toy Story") == "Woody Toy Story"
    unchecked = Candidate("u", "Woody in Toy Story 4K wallpaper", "bing", 0.0, 1920, 1080)
    assert score(unchecked, "Woody (voice)", "Toy Story", faces=False) is not None
    # without faces, the film named is not enough: the character must be
    film_only = Candidate("u", "Toy Story wallpaper", "bing", 0.0, 1920, 1080)
    assert score(film_only, "Woody (voice)", "Toy Story", faces=False) is None
    voice_only = Candidate("u", "Tom Hanks voice actor", "bing", 0.0, 1920, 1080)  # « voice » is no name
    assert score(voice_only, "Woody (voice)", "Toy Story", faces=False) is None


class Drawn:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.fetched: list[str] = []

    async def images(self, query: str, limit: int = 30) -> list[Any]:
        from portalab.capabilities.media import ImageHit

        self.queries.append(query)
        return [
            ImageHit("https://a/poster.jpg", "Toy Story poster", 1000, 1500, "bing"),
            ImageHit("https://a/small.jpg", "Woody Toy Story", 200, 150, "bing"),
            ImageHit("https://a/woody.jpg", "Woody - Toy Story 4K wallpaper", 3840, 2160, "bing"),
        ]

    async def fetch(self, url: str) -> bytes:
        self.fetched.append(url)
        return b"woody"


async def test_an_animated_works_character_and_the_check_switched_off(database: Database) -> None:
    from portalab.capabilities.media import IMAGE_SEARCH
    from portalab.modules.cards.search import RoleSearch

    capabilities = new_registry()
    cartoon = replace(work("Toy Story", 9000, "US", ["Tom Hanks"]), genres=["Animation", "Family"])
    capabilities.provide(CARD_SOURCES, Sources([cartoon]), instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    async with database.unit_of_work() as uow:
        await uow.session.execute(
            Card.__table__.update()
            .where(Card.kind == "cast")
            .values(role_checked_at=NOW, role="Woody (voice)")
        )
        animated = (await uow.session.execute(CardSet.__table__.select())).one().animated
    assert animated is True
    drawn, blobs = Drawn(), Blobs()
    capabilities.provide(IMAGE_SEARCH, drawn, instance_ref="searxng", owner="test")

    class NoFaces(Matcher):
        async def ready(self) -> bool:
            raise AssertionError("an animated work's faces are never compared")

    search = RoleSearch(database, capabilities, NoFaces(), blobs, face_check=lambda: True)  # type: ignore[arg-type]
    assert await search.run() == 1
    assert drawn.queries == ["Woody Toy Story"]  # the character and the work, not the actor
    assert drawn.fetched == ["https://a/woody.jpg"]  # named, large enough


async def test_the_face_check_switched_off(database: Database) -> None:
    from portalab.capabilities.media import IMAGE_SEARCH
    from portalab.modules.cards.search import RoleSearch

    capabilities = new_registry()
    film = work("Top Gun: Maverick", 11000, "US", ["Tom Cruise"])
    capabilities.provide(CARD_SOURCES, Sources([film]), instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    async with database.unit_of_work() as uow:
        await uow.session.execute(
            Card.__table__.update().where(Card.kind == "cast").values(role_checked_at=NOW, role="Maverick")
        )
    web, blobs = Web(), Blobs()
    capabilities.provide(IMAGE_SEARCH, web, instance_ref="searxng", owner="test")
    search = RoleSearch(database, capabilities, Matcher(), blobs, face_check=lambda: False)  # type: ignore[arg-type]
    assert await search.run() == 1
    assert web.queries == ["Tom Cruise Maverick Top Gun: Maverick"]  # the actor still named
    assert list(blobs.kept.values()) == [b"face:cruise jet"]  # the page naming Maverick, not the premiere


class FilmMatcher(Matcher):
    """Faces as their bytes say, each large and sharp enough; a crop keeps the image, marked."""

    def look(self, data: bytes) -> Any:
        from portalab.modules.cards.faces import Face, Looked

        who = [p.removeprefix("face:") for p in data.decode().split() if p.startswith("face:")]
        return Looked(tuple(Face(w, 0.05, (600, 200, 120, 150), 120.0) for w in who), 1280, 720)

    def crop(self, data: bytes, box: tuple[int, int, int, int]) -> bytes:
        return data + f" crop:{box[2]}x{box[3]}".encode()


class FilmSources(Sources):
    def __init__(self, works: list[CardWork], frames: list[bytes] | None) -> None:
        super().__init__(works)
        self.shots = frames
        self.taken = 0

    async def image(self, ref: str, size: str) -> bytes:
        return f"face:{ref.strip('/').removesuffix('.jpg')}".encode()  # each actor's portrait

    async def frames(self, object_id: UUID, at: list[float]) -> list[bytes] | None:
        self.taken += 1
        assert len(at) == 96 and 0 < at[0] < at[-1] < 1  # spread over the film, credits left out
        return self.shots


class Plex:
    async def frames(self, external_id: str, at: list[float]) -> Any:  # never asked: the sources are
        raise AssertionError


async def test_an_actors_character_taken_from_the_film_itself(database: Database) -> None:
    """Issue 230: the film's own images, each actor's face found on them, framed — one pass for the whole
    cast; an actor not seen is left to the web search, and the film is never taken again."""
    from portalab.capabilities.media import IMAGE_SEARCH, VIDEO_FRAMES
    from portalab.modules.cards.frames import FilmFrames
    from portalab.modules.cards.search import RoleSearch

    capabilities = new_registry()
    film = work("Top Gun: Maverick", 11000, "US", ["Tom Cruise", "Miles Teller", "Jennifer Connelly"])
    sources = FilmSources([film], [b"face:teller", b"face:cruise face:teller", b"a sky"])
    capabilities.provide(CARD_SOURCES, sources, instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    async with database.unit_of_work() as uow:  # TMDB was asked and had nothing; their portraits are known
        for name, art in (("Tom Cruise", "/cruise.jpg"), ("Miles Teller", "/teller.jpg")):
            await uow.session.execute(
                Card.__table__.update().where(Card.name == name).values(role_checked_at=NOW, art=art)
            )
        await uow.session.execute(
            Card.__table__.update()
            .where(Card.name == "Jennifer Connelly")
            .values(role_checked_at=NOW, art="/connelly.jpg")
        )
    blobs = Blobs()
    frames = FilmFrames(database, capabilities, FilmMatcher(), blobs)  # type: ignore[arg-type]
    web = Web()
    capabilities.provide(IMAGE_SEARCH, web, instance_ref="searxng", owner="test")
    search = RoleSearch(
        database,
        capabilities,
        FilmMatcher(),
        blobs,
        frames_first=frames.available,  # type: ignore[arg-type]
    )
    assert await frames.run() == 0 and sources.taken == 0  # no media server can show the film yet
    capabilities.provide(VIDEO_FRAMES, Plex(), instance_ref="plex", owner="test")
    assert await search.run() == 0 and web.queries == []  # the film itself comes first
    assert await frames.run() == 2 and sources.taken == 1
    async with database.session() as session:
        rows = (await session.execute(Card.__table__.select().where(Card.kind == "cast"))).all()
    cards = {r.name: r for r in rows}
    assert blobs.kept[cards["Tom Cruise"].role_art.removeprefix("blob:")].startswith(b"face:cruise face:")
    assert blobs.kept[cards["Miles Teller"].role_art.removeprefix("blob:")] == b"face:teller crop:640x480"
    assert cards["Jennifer Connelly"].role_art is None  # not seen in the film
    assert all(c.frame_checked_at is not None for c in cards.values())
    assert await frames.run() == 0 and sources.taken == 1  # taken once: the cache
    await search.run()
    assert web.queries == ["Jennifer Connelly as Jennifer Connelly Top Gun: Maverick"]  # only her, on the web


class Tvdb:
    """TheTVDB's roles: by actor's name (accents and « (voice) » aside), else by character."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, dict[str, str]]] = []

    async def characters(self, kind: str, ids: dict[str, str]) -> list[Any]:
        from portalab.capabilities.media import CharacterImage

        self.asked.append((kind, dict(ids)))
        return [
            CharacterImage("Tom Cruise", "Maverick", "/banners/person/1/maverick.jpg", 1),
            CharacterImage("Someone Else", "as Miles Teller", "/banners/person/2/rooster.jpg", 2),
        ]

    async def fetch_character(self, ref: str) -> bytes:
        return f"role:{ref}".encode()


async def test_a_roles_own_image_from_the_community_database(database: Database) -> None:
    """Issue 231: each role's own image (TheTVDB), matched by its actor's name else by its character — it wins
    over any image found before and is never replaced by TMDB's; the web is an option, off by default."""
    from portalab.capabilities.media import CHARACTERS
    from portalab.modules.cards.characters import CharacterSheets, match, norm
    from portalab.modules.cards.search import RoleSearch
    from portalab.modules.cards.settings import CardsConfig

    assert norm("Zoë Saldaña (voice)") == "zoe saldana"
    capabilities = new_registry()
    film = work("Top Gun: Maverick", 11000, "US", ["Tom Cruise", "Miles Teller", "Jennifer Connelly"])
    sources = Sources([film])
    capabilities.provide(CARD_SOURCES, sources, instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    async with database.unit_of_work() as uow:  # a web image found before for him
        await uow.session.execute(
            Card.__table__.update().where(Card.name == "Tom Cruise").values(role_art="blob:cards/" + "0" * 64)
        )
    blobs = Blobs()
    sheets = CharacterSheets(database, capabilities, blobs)  # type: ignore[arg-type]
    assert await sheets.run() == 0 and not sheets.available()  # no database connected: nothing marked
    tvdb = Tvdb()
    capabilities.provide(CHARACTERS, tvdb, instance_ref="tvdb", owner="test")
    assert await sheets.run() == 2
    assert tvdb.asked[0][0] == "movie" and tvdb.asked[0][1]["tmdb"] == film.tmdb
    async with database.session() as session:
        rows = (await session.execute(Card.__table__.select().where(Card.kind == "cast"))).all()
    cards = {r.name: r for r in rows}
    assert (
        blobs.kept[cards["Tom Cruise"].role_art.removeprefix("blob:")]
        == b"role:/banners/person/1/maverick.jpg"
    )
    assert blobs.kept[cards["Miles Teller"].role_art.removeprefix("blob:")].endswith(
        b"rooster.jpg"
    )  # by role
    assert cards["Jennifer Connelly"].role_art is None
    assert all(c.character_checked_at is not None for c in cards.values())
    assert await sheets.run() == 0 and len(tvdb.asked) == 1  # kept: the cache
    # TMDB's stills come later: the role's own image stays
    await RoleArt(database, capabilities).run()
    async with database.session() as session:
        cruise = (await session.execute(Card.__table__.select().where(Card.name == "Tom Cruise"))).one()
    assert cruise.role_art == cards["Tom Cruise"].role_art
    assert match([("a", "X", None)], []) == {}
    # the web: off by default, nothing asked
    assert CardsConfig().web_search is False
    web = Web()
    capabilities.provide(IMAGE_SEARCH_KEY, web, instance_ref="searxng", owner="test")
    off = RoleSearch(database, capabilities, Matcher(), blobs, enabled=lambda: False)  # type: ignore[arg-type]
    assert await off.run() == 0 and web.queries == []


IMAGE_SEARCH_KEY = "media.image_search"


async def test_a_sets_characters_looked_for_again_by_every_source_in_order(
    database: Database, tmp_path: Any
) -> None:
    """Issue 231: an administrator's « look again »: the set's images forgotten, then each source in its
    order fills only the cards still without one — TheTVDB, TMDB, the film, the web (off by default)."""
    from portalab.capabilities.media import CHARACTERS
    from portalab.modules.cards.module import CardsModule

    capabilities = new_registry()
    film = work("Top Gun: Maverick", 11000, "US", ["Tom Cruise", "Miles Teller", "Jennifer Connelly"])
    capabilities.provide(CARD_SOURCES, Sources([film]), instance_ref="t", owner="test")
    capabilities.provide(CHARACTERS, Tvdb(), instance_ref="tvdb", owner="test")
    module = CardsModule(database, capabilities, blobs=Blobs(), root=tmp_path)  # type: ignore[arg-type]
    await module.forge.sync()
    async with database.unit_of_work() as uow:  # an image found before for Jennifer Connelly
        await uow.session.execute(
            Card.__table__.update().where(Card.name == "Jennifer Connelly").values(role_art="blob:cards/old")
        )
    key = str(film.object_id)
    # TheTVDB has Tom Cruise's and Miles Teller's roles; TMDB a still of Tom Cruise (TheTVDB's stays: none
    # given); the
    # film cannot be shown, the web is off: Jennifer Connelly's old image is forgotten
    assert await module.look_again(key) == {"tvdb": 2, "tmdb": 0, "film": 0, "web": 0}
    async with database.session() as session:
        rows = (await session.execute(Card.__table__.select().where(Card.kind == "cast"))).all()
    cards = {r.name: r for r in rows}
    assert cards["Tom Cruise"].role_art.startswith("blob:")  # TheTVDB's, not TMDB's still
    assert cards["Jennifer Connelly"].role_art is None


async def test_a_trial_pack_among_the_works_whose_characters_were_looked_for(database: Database) -> None:
    """Issue 229: an administrator's trial pack — six cards, drawn among the works whose characters were
    looked for only, opened like any pack."""
    capabilities = new_registry()
    looked, other = work("Looked For", 9000, "US", ["A", "B"]), work("Not Yet", 9000, "US", ["C", "D"])
    capabilities.provide(CARD_SOURCES, Sources([looked, other]), instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    async with database.unit_of_work() as uow:
        await uow.session.execute(
            Card.__table__.update()
            .where(Card.set_key == str(looked.object_id))
            .values(character_checked_at=NOW)
        )
        user = uuid4()
        await uow.session.execute(INSERT_USER, {"id": user, "login": f"u{user.hex[:8]}"})
    packs = Packs(database, capabilities, rng=random.Random(4))  # noqa: S311 — a fixed draw for the test
    pack_id = await packs.trial(user)
    async with database.session() as session:
        copies = (
            await session.execute(
                Card.__table__.select().join(Copy, Copy.card_id == Card.id).where(Copy.pack_id == pack_id)
            )
        ).all()
    assert len(copies) == 6 and {c.set_key for c in copies} == {str(looked.object_id)}
    assert await packs.open(user, pack_id) is not None


async def test_a_contents_boosters_given_once_per_member(database: Database) -> None:
    """Issue 234: a reward rule's boosters of a content — its work's, once per member and content."""
    capabilities = new_registry()
    film = work("Top Gun: Maverick", 11000, "US", ["Tom Cruise"])
    capabilities.provide(CARD_SOURCES, Sources([film]), instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    user = uuid4()
    async with database.unit_of_work() as uow:
        await uow.session.execute(INSERT_USER, {"id": user, "login": f"u{user.hex[:8]}"})
    packs = Packs(database, capabilities, rng=random.Random(5))  # noqa: S311 — deterministic test data
    boosters = ContentBoosters(packs)
    for index in range(12):  # an administrator's trial packs are no reward: they leave the day's share whole
        await packs.give(user, "trial", None, f"trial:{index}")
    assert await boosters.give(user, film.object_id, 2, "rule:films:1") == 2
    assert await boosters.give(user, film.object_id, 2, "rule:films:2") == 0  # watched again: given already
    assert await boosters.give(user, uuid4(), 1, "rule:films:3") == 0  # a content without cards
    unopened = [p for p in await packs.unopened(user) if p.source == "content"]
    assert len(unopened) == 2 and {p.set_key for p in unopened} == {str(film.object_id)}
    assert unopened[0].detail["object"] == str(film.object_id)


async def test_a_shops_booster_draws_among_the_works_it_names(database: Database) -> None:
    """Issue 234: a booster of cards bought in the shop — sealed in the inventory, its cards drawn among the
    works of its genre and edition only; one naming no work is not sold."""
    capabilities = new_registry()
    space = replace(work("Interstellar", 9000, "US", ["Matthew"]), genres=("Science-Fiction",), year=2014)
    old = replace(work("Alien", 8000, "US", ["Sigourney"]), genres=("Science-Fiction",), year=1979)
    comedy = replace(work("OSS 117", 3000, "FR", ["Jean"]), genres=("Comédie",), year=2006)
    capabilities.provide(CARD_SOURCES, Sources([space, old, comedy]), instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    user = uuid4()
    async with database.unit_of_work() as uow:
        await uow.session.execute(INSERT_USER, {"id": user, "login": f"u{user.hex[:8]}"})
    packs = Packs(database, capabilities, rng=random.Random(7))  # noqa: S311 — deterministic test data
    handler = CardBoosterHandler(packs)

    def bought(**payload: Any) -> OwnershipView:
        return OwnershipView(uuid4(), user, "sf_stream", "card_booster", payload)

    assert (await handler.activate(bought(family="sf", edition="tiles", cards="5"))).state == "active"
    assert (await handler.activate(bought(family="family", edition="film"))).state == "incompatible"
    unopened = await packs.unopened(user)
    assert len(unopened) == 1 and unopened[0].source == "shop"
    async with database.session() as session:
        sets = (
            (
                await session.execute(
                    Card.__table__.select()
                    .with_only_columns(Card.set_key)
                    .join(Copy, Copy.card_id == Card.id)
                    .where(Copy.pack_id == unopened[0].id)
                )
            )
            .scalars()
            .all()
        )
    assert len(sets) == 5 and set(sets) == {str(space.object_id)}  # science fiction since 2010 only


async def test_a_booster_guarantees_its_rarity(database: Database) -> None:
    """Issue 255: a booster of the shop that guarantees a rarity holds a card of it — one that names a rarity
    its works have none of is not sold."""
    capabilities = new_registry()
    film = work("Dune", 12000, "US", ["Timothée", "Zendaya", "Rebecca", "Oscar", "Josh"])
    capabilities.provide(CARD_SOURCES, Sources([film]), instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    async with database.session() as session:
        present = set((await session.execute(select(Card.rarity))).scalars())
    best = next(r for r in ("legendary", "epic", "rare") if r in present)
    user = uuid4()
    async with database.unit_of_work() as uow:
        await uow.session.execute(INSERT_USER, {"id": user, "login": f"u{user.hex[:8]}"})
    packs = Packs(database, capabilities, rng=random.Random(11))  # noqa: S311 — deterministic test data
    handler = CardBoosterHandler(packs)
    assert booster_of({"rarity": "mythic", "cards": "3"}) == {
        "cards": 3
    }  # an unknown rarity guarantees nothing
    for attempt in range(6):  # the odds alone would seldom give it six times running
        ownership = OwnershipView(
            uuid4(), user, f"rarity_{attempt}", "card_booster", {"rarity": best, "cards": 3}
        )
        assert (await handler.activate(ownership)).state == "active"
    async with database.session() as session:
        rarities = (
            await session.execute(
                select(Copy.pack_id, Card.rarity)
                .join(Card, Card.id == Copy.card_id)
                .where(Copy.user_id == user)
            )
        ).all()
    by_pack: dict[Any, set[str]] = {}
    for pack_id, rarity in rarities:
        by_pack.setdefault(pack_id, set()).add(rarity)
    assert len(by_pack) == 6 and all(best in found for found in by_pack.values())
    absent = [r for r in ("rare", "epic", "legendary") if r not in present]
    if absent:
        ownership = OwnershipView(uuid4(), user, "absent", "card_booster", {"rarity": absent[0]})
        assert (await handler.activate(ownership)).state == "incompatible"


async def test_a_genre_booster_and_a_booster_signature_frame(database: Database) -> None:
    """Issue 296: a genre booster draws among the works of that main genre; a booster may sign its cards with
    its own frame — on a card in its base frame only, a rarity booster's on the card it guarantees."""
    capabilities = new_registry()
    horror = replace(
        work("Shining", 9000, "US", ["Jack", "Shelley", "Danny"]), genres=("Horreur", "Thriller")
    )
    thriller = replace(work("Seven", 8000, "US", ["Brad", "Morgan"]), genres=("Thriller", "Horreur"))
    capabilities.provide(CARD_SOURCES, Sources([horror, thriller]), instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    async with database.session() as session:
        genres = dict((await session.execute(select(CardSet.name, CardSet.genre))).all())
    assert genres == {"Shining": "horror", "Seven": "thriller"}  # its first genre, not the strongest
    user = uuid4()
    async with database.unit_of_work() as uow:
        await uow.session.execute(INSERT_USER, {"id": user, "login": f"u{user.hex[:8]}"})
    packs = Packs(database, capabilities, rng=random.Random(5))  # noqa: S311 — deterministic test data
    handler = CardBoosterHandler(packs)
    assert booster_of({"genre": "horror", "signature": "Bad Look!", "cards": 3}) == {
        "genre": "horror",
        "cards": 3,
    }
    for attempt in range(12):
        payload = {"genre": "horror", "signature": "tenebres", "cards": 3}
        assert (
            await handler.activate(OwnershipView(uuid4(), user, f"h{attempt}", "card_booster", payload))
        ).state == "active"
    async with database.session() as session:
        drawn = (
            await session.execute(
                select(CardSet.name, Copy.variant)
                .join(Card, Card.set_key == CardSet.key)
                .join(Copy, Copy.card_id == Card.id)
                .where(Copy.user_id == user)
            )
        ).all()
    assert {name for name, _ in drawn} == {"Shining"}
    signed = [v for _, v in drawn if v.startswith("signature")]
    assert signed and all(v in ("signature:tenebres", "signature_foil:tenebres") for v in signed)
    # the rest in its own versions
    assert {v for _, v in drawn} - set(signed) <= set(VARIANTS)


class Published:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any], str | None]] = []

    async def publish(self, session: Any, event_type: str, metadata: Any = None, **kwargs: Any) -> None:
        self.events.append((event_type, dict(metadata or {}), kwargs.get("dedup_key")))


async def test_a_booster_opened_and_a_collection_completed(database: Database) -> None:
    """Issue 234: what the achievements count — a booster opened (its rarest card, its legendaries, its foils)
    and every card of a work's set owned, once."""
    capabilities = new_registry()
    film = work("Top Gun: Maverick", 11000, "US", ["Tom Cruise"])
    capabilities.provide(CARD_SOURCES, Sources([film]), instance_ref="t", owner="test")
    await CardForge(database, capabilities).sync()
    user = uuid4()
    async with database.unit_of_work() as uow:
        await uow.session.execute(INSERT_USER, {"id": user, "login": f"u{user.hex[:8]}"})
    published = Published()
    packs = Packs(database, capabilities, rng=random.Random(2), events=published)  # type: ignore[arg-type]  # noqa: S311
    first = await packs.give(user, "content", str(film.object_id), "k1", size=1)
    assert first is not None
    await packs.open(user, first)
    assert [e[0] for e in published.events] == ["cards.pack_opened"]
    assert published.events[0][1]["cards"] == 1 and published.events[0][1]["source"] == "content"
    # a second booster holding every card of the set: the collection is complete
    second = await packs.give(user, "content", str(film.object_id), "k2", size=1)
    assert second is not None
    async with database.unit_of_work() as uow:
        cards = (
            await uow.session.execute(Card.__table__.select().where(Card.set_key == str(film.object_id)))
        ).all()
        for card in cards:
            uow.session.add(
                Copy(user_id=user, card_id=card.id, variant="foil", pack_id=second, acquired_at=NOW)
            )
    await packs.open(user, second)
    await packs.open(user, second)  # opened already: nothing again
    kinds = [e[0] for e in published.events]
    assert kinds == ["cards.pack_opened", "cards.pack_opened", "cards.set_completed"]
    done = published.events[2][1]
    assert done["set"] == str(film.object_id) and done["size"] == len(cards) and done["kind"] == "movie"
    assert published.events[1][1]["foil"] == len(cards)
