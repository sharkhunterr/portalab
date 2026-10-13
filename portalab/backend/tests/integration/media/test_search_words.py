"""#92 — the media search finds a title by every word of a query, in any order and despite a typo, through
its series and the people behind it (author, narrator, director, cast — whichever apostrophe is typed), says
whom it found, and filters by subtype (film, book, audiobook…) with counts over every match."""

from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.media import PEOPLE, PersonCredit, PersonRecord
from portalab.capabilities.media.testkit import library_record
from portalab.capabilities.search import ParsedQuery
from portalab.core.authz_port import Principal
from portalab.modules.media.catalog import CatalogQuery
from portalab.modules.media.matching import fold, words
from portalab.modules.media.models import ExternalId, MediaObject, ObjectMetadata
from portalab.modules.media.people import People
from portalab.modules.media.providers.search import MediaSearchProvider, PeopleSearchProvider
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

RSQ = "\u2019"  # the typographic apostrophe


def _query(text: str, **filters: tuple[str, ...]) -> ParsedQuery:
    return ParsedQuery(text=text, normalized=fold(text), terms=tuple(fold(text).split()), filters=filters)


async def _library(app: FastAPI, media: MediaHarness) -> tuple[MediaSearchProvider, Principal]:
    people = await users(app, media, "zoe")
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            library_record(
                "a2",
                kind="audiobook",
                title="L'assassin du roi",
                series="L'Assassin Royal",
                series_position=2,
                authors=["Robin Hobb"],
                narrators=["Sylvain Agaësse"],
                people=["Robin Hobb", "Sylvain Agaësse"],
            ),
            library_record(
                "a1",
                kind="audiobook",
                title="L'apprenti assassin",
                series="L'Assassin Royal",
                series_position=1,
                authors=["Robin Hobb"],
                people=["Robin Hobb"],
            ),
            library_record("b1", kind="book", title="Le Royaume", authors=["Emmanuel Carrère"]),
            library_record("m1", title="Les Banshees d'Inisherin", year=2022, people=["Brendan Gleeson"]),
            library_record("m2", title="Dune", year=2021, directors=["Denis Villeneuve"]),
            library_record("m3", title="Le Royal Tenenbaums", year=2001),
        ],
        one,
    )
    async with media.database.unit_of_work() as uow:
        banshees = (
            await uow.session.execute(select(MediaObject).where(MediaObject.title.like("Les Banshees%")))
        ).scalar_one()
        uow.session.add(
            ObjectMetadata(
                object_id=banshees.id,
                provider="tmdb",
                status="found",
                language="fr",
                data={"people": [{"name": "Kerry Condon", "department": "cast"}]},
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    provider = MediaSearchProvider(
        CatalogQuery(media.database, media.module.authorizer), media.module.authorizer
    )
    return provider, Principal(user_id=people["zoe"])


async def _titles(provider: MediaSearchProvider, principal: Principal, text: str, **filters: tuple[str, ...]):
    result = await provider.search(_query(text, **filters), principal, LocaleContext(), limit=20, cursor=None)
    return [item.title for item in result.items], result


def test_words_are_folded_like_the_index() -> None:
    assert fold(f"L{RSQ}Assassin_royal — Tome 1") == "l assassin royal tome 1"
    assert words("l'assassin royal") == ["assassin", "royal"]
    assert words(f"O{RSQ}Dowd") == ["dowd"]
    assert words("Œuvre") == ["oeuvre"]


async def test_several_words_in_any_order_and_a_typo(app: FastAPI, media: MediaHarness) -> None:
    provider, zoe = await _library(app, media)
    series = ["L'apprenti assassin", "L'assassin du roi"]  # through their series, in its order
    for text in ("assassin royal", "royal assassin", "assasin royal", f"L{RSQ}Assassin Royal"):
        titles, _ = await _titles(provider, zoe, text)
        assert titles[:2] == series, text
        assert "Le Royal Tenenbaums (2001)" not in titles  # « royal » alone is not enough
    titles, _ = await _titles(provider, zoe, "royal")
    assert titles[0] == "Le Royal Tenenbaums (2001)"  # in the title before in a series


async def test_found_by_its_people_whatever_the_apostrophe(app: FastAPI, media: MediaHarness) -> None:
    provider, zoe = await _library(app, media)
    titles, result = await _titles(provider, zoe, "robin hobb")
    assert set(titles) == {"L'apprenti assassin", "L'assassin du roi"}
    assert {(i.facets["person"], i.facets["role"]) for i in result.items} == {("Robin Hobb", "author")}
    _, result = await _titles(provider, zoe, "agaesse")  # the narrator, accents forgiven
    assert [(i.facets["person"], i.facets["role"]) for i in result.items] == [("Sylvain Agaësse", "narrator")]
    _, result = await _titles(provider, zoe, "villeneuve")
    assert [(i.title, i.facets["role"]) for i in result.items] == [("Dune (2021)", "director")]
    _, result = await _titles(provider, zoe, "kerry condon")  # the metadata provider's cast
    assert [(i.facets["person"], i.facets["role"]) for i in result.items] == [("Kerry Condon", "cast")]
    for text in ("banshees d'inisherin", f"banshees d{RSQ}inisherin", "Banshees dInisherin"):
        titles, _ = await _titles(provider, zoe, text)
        assert titles == ["Les Banshees d'Inisherin (2022)"], text
    titles, result = await _titles(provider, zoe, "Carrère")
    assert titles == ["Le Royaume"] and result.items[0].facets["role"] == "author"
    _, result = await _titles(provider, zoe, "dune")
    assert "person" not in result.items[0].facets  # found by its title: nobody to name


async def test_subtypes_filter_and_count_every_match(app: FastAPI, media: MediaHarness) -> None:
    provider, zoe = await _library(app, media)
    assert "subtype" in {facet.key for facet in provider.facets()}
    titles, result = await _titles(provider, zoe, "ro")
    counts = result.facets["subtype"]
    assert counts == {"audiobook": 2, "book": 1, "movie": 1}  # « roi », « robin », « royaume », « royal »
    titles, result = await _titles(provider, zoe, "ro", subtype=("audiobook", "book"))
    assert sorted(titles) == ["L'apprenti assassin", "L'assassin du roi", "Le Royaume"]
    assert result.facets["subtype"] == counts  # the other subtypes stay offered
    titles, _ = await _titles(provider, zoe, "", subtype=("movie",))
    assert len(titles) == 3


async def test_people_are_found_and_have_a_page(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    """The user's wish: the name of an actor, a director, an author or a narrator shows the person — a
    section of its own — and opens their page of titles, by role."""
    _, zoe = await _library(app, media)
    people = PeopleSearchProvider(People(media.database), media.module.authorizer)
    result = await people.search(_query("robin hob"), zoe, LocaleContext(), limit=5, cursor=None)
    [hobb] = result.items
    assert (hobb.title, hobb.url_ref) == ("Robin Hobb", "/media/people/Robin%20Hobb")
    assert hobb.facets["roles"] == "author" and hobb.facets["titles"] == "2"
    for text, role in (("villeneuv", "director"), ("agaesse", "narrator"), ("kerry condon", "cast")):
        found = await people.search(_query(text), zoe, LocaleContext(), limit=5, cursor=None)
        assert [item.facets["roles"] for item in found.items] == [role], text
    gleeson = await people.search(_query("Brendan"), zoe, LocaleContext(), limit=5, cursor=None)
    assert [item.title for item in gleeson.items] == ["Brendan Gleeson"]
    assert not (await people.search(_query("dune"), zoe, LocaleContext(), limit=5, cursor=None)).items

    await login(client, "zoe")
    page = (await client.get("/api/v1/media/person", params={"name": "robin hobb"})).json()
    assert page["name"] == "Robin Hobb" and page["roles"] == ["author"] and page["titles"] == 2
    assert [card["title"] for card in page["credits"][0]["items"]] == [
        "L'apprenti assassin",
        "L'assassin du roi",
    ]
    page = (await client.get("/api/v1/media/person", params={"name": "Sylvain Agaësse"})).json()
    assert [credit["role"] for credit in page["credits"]] == ["narrator"]
    missing = await client.get("/api/v1/media/person", params={"name": "Nobody"})
    assert missing.status_code == 404


class _Source:
    """A ``media.people`` service: what it knows of a person, and their portrait."""

    def __init__(self, record: PersonRecord | None) -> None:
        self.record = record
        self.asked: list[tuple[str, dict[str, str]]] = []

    async def person(self, name: str, ids: Mapping[str, str], language: str) -> PersonRecord | None:
        self.asked.append((name, dict(ids)))
        return self.record if self.record and self.record.name == name else None

    async def portrait(self, ref: str, size: str) -> bytes:
        return b"\xff\xd8portrait"


async def test_a_person_page_is_enriched_by_every_configured_service(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    """The user's wish: whichever services are configured (TMDB, Seerr, Jellyfin, Grimmory…), the page
    tells what they know — the biography from one, the filmography from another — and each title's
    standing in the library (available, not available, to ask for)."""
    await _library(app, media)
    films = PersonRecord(
        ids={"tmdb": "77"},
        name="Denis Villeneuve",
        known_for="Directing",
        credits=[
            PersonCredit(
                tmdb_id="438631",
                kind="movie",
                title="Dune",
                year=2021,
                department="directing",
                role="Director",
                vote_count=12000,
            ),
            PersonCredit(
                tmdb_id="335984",
                kind="movie",
                title="Blade Runner 2049",
                year=2017,
                department="directing",
                role="Director",
                vote_count=14000,
            ),
        ],
    )
    bio = PersonRecord(ids={}, name="Denis Villeneuve", biography="A Québécois director.", portrait="p1")
    async with media.database.unit_of_work() as uow:
        dune = (
            await uow.session.execute(select(MediaObject).where(MediaObject.title == "Dune"))
        ).scalar_one()
        uow.session.add(ExternalId(scheme="tmdb", value="438631", object_id=dune.id))
    rich, short = _Source(films), _Source(bio)
    seerr, jelly = media.service(7, "seerr"), media.service(8, "jellyfin")
    for service, source, connector in ((seerr, rich, "seerr"), (jelly, short, "jellyfin")):
        media.ev.full.identity.capabilities.provide(
            PEOPLE,
            source,
            instance_ref=str(service.service_id),
            owner=f"service:{service.service_id}",
            metadata={"connector": connector, "name": connector.title()},
        )
    await login(client, "zoe")
    page = (await client.get("/api/v1/media/person", params={"name": "Denis Villeneuve"})).json()
    assert page["profile"]["biography"] == "A Québécois director."  # from Jellyfin
    assert page["profile"]["known_for"] == "Directing"  # from Seerr
    assert sorted(page["sources"]) == ["Jellyfin", "Seerr"]
    assert [(c["title"], c["status"]) for c in page["filmography"]] == [
        ("Dune", "available"),
        ("Blade Runner 2049", "missing"),
    ]
    assert page["filmography"][0]["route"] == f"/media/{dune.id}"
    assert [c["title"] for c in page["known_for"]] == ["Blade Runner 2049", "Dune"]  # the most voted first
    assert page["counts"] == {"available": 1, "missing": 1}
    assert page["portrait"].startswith("/api/v1/media/person/portrait?service=")
    portrait = await client.get(page["portrait"])
    assert portrait.status_code == 200 and portrait.content == b"\xff\xd8portrait"
    # someone no service knows: the page is still there, with the library's own titles
    page = (await client.get("/api/v1/media/person", params={"name": "Robin Hobb"})).json()
    assert page["titles"] == 2 and page["filmography"] == []
