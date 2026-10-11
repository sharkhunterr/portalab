"""#67 — media search results tell what a title looks like and where it stands: its poster, its first
genres and its state (available, requested — a request in progress — or not available)."""

from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy import select, update

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.media.testkit import PNG_1PX, library_record
from portalab.capabilities.search import ParsedQuery
from portalab.core.authz_port import Principal
from portalab.modules.media.catalog import CatalogQuery
from portalab.modules.media.models import MediaObject, MediaRequest
from portalab.modules.media.providers.search import MediaSearchProvider
from tests.integration.media.conftest import MediaHarness, users


async def test_results_show_poster_genres_and_state(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "zoe")
    one = media.service(1)
    media.library(one).images["p"] = PNG_1PX
    await media.module.library.upsert(
        [
            library_record("101", title="Dune", year=2021, genres=["Sci-Fi", "Adventure"], image="p"),
            library_record("102", title="Dune Messiah", year=2027),
            library_record("103", title="Dune Prophecy", kind="series", year=2024),
        ],
        one,
    )
    now = datetime(2026, 10, 10, tzinfo=UTC)
    async with media.database.unit_of_work() as uow:
        rows = {o.title: o for o in (await uow.session.execute(select(MediaObject))).scalars()}
        await uow.session.execute(
            update(MediaObject)
            .where(MediaObject.id.in_([rows["Dune Messiah"].id, rows["Dune Prophecy"].id]))
            .values(available=False)
        )
        uow.session.add(
            MediaRequest(
                object_id=rows["Dune Messiah"].id,
                external_ref={"title": "Dune Messiah"},
                service_id=uuid4(),
                state="processing",
                source_state="processing",
                counted="base",
                requested_at=now,
                updated_at=now,
            )
        )
    assert await media.module.images.fetch(rows["Dune"].id)  # the poster, downloaded
    provider = MediaSearchProvider(
        CatalogQuery(media.database, media.module.authorizer), media.module.authorizer
    )
    query = ParsedQuery(text="dune", normalized="dune", terms=("dune",))
    result = await provider.search(
        query, Principal(user_id=people["zoe"]), LocaleContext(), limit=10, cursor=None
    )
    facets = {item.title: item.facets for item in result.items}
    assert facets["Dune (2021)"]["status"] == "available"
    assert facets["Dune (2021)"]["genres"] == "Adventure, Sci-Fi"
    assert facets["Dune (2021)"]["image"]
    assert facets["Dune Messiah (2027)"]["status"] == "requested"
    assert facets["Dune Prophecy (2024)"]["status"] == "unavailable"
    assert "image" not in facets["Dune Messiah (2027)"]


async def test_the_most_relevant_titles_come_first(app: FastAPI, media: MediaHarness) -> None:
    """#67: « Star Wars » finds the film before « 095 [An +001] Star Wars 01 » (A to Z alone put the
    numbered books first) — exact, then starting with, then a word starting with; films before books."""
    people = await users(app, media, "zoe")
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            library_record("b1", kind="book", title="095 [An +001] Star Wars 01 - Dans l'ombre de Yavin"),
            library_record("b2", kind="book", title="Star Wars: Thrawn"),
            library_record("m1", title="Star Wars", year=1977),
            library_record("s1", kind="series", title="Star Wars: Andor", year=2022),
            library_record("m2", title="Rogue One: A Star Wars Story", year=2016),
        ],
        one,
    )
    provider = MediaSearchProvider(
        CatalogQuery(media.database, media.module.authorizer), media.module.authorizer
    )
    query = ParsedQuery(text="star wars", normalized="star wars", terms=("star", "wars"))
    result = await provider.search(
        query, Principal(user_id=people["zoe"]), LocaleContext(), limit=10, cursor=None
    )
    assert [item.title for item in result.items] == [
        "Star Wars (1977)",
        "Star Wars: Andor (2022)",
        "Star Wars: Thrawn",
        "Rogue One: A Star Wars Story (2016)",  # a word starts with it: the film before the book
        "095 [An +001] Star Wars 01 - Dans l'ombre de Yavin",
    ]


async def test_suggestions_take_each_types_best(app: FastAPI, media: MediaHarness) -> None:
    """#67: the header's suggestions draw each type's best — a book still comes when four games and six
    films fill the first page of results."""
    people = await users(app, media, "zoe")
    one = media.service(1)
    media.library(one)
    records = [library_record(f"g{n}", kind="game", title="Star Wars", year=1990 + n) for n in range(4)]
    records += [library_record(f"m{n}", title=f"Star Wars, episode {n}", year=2000 + n) for n in range(6)]
    records.append(library_record("b1", kind="book", title="095 [An +001] Star Wars 01"))
    await media.module.library.upsert(records, one)
    provider = MediaSearchProvider(
        CatalogQuery(media.database, media.module.authorizer), media.module.authorizer
    )
    query = ParsedQuery(text="star wars", normalized="star wars", terms=("star", "wars"))
    page = await provider.search(
        query, Principal(user_id=people["zoe"]), LocaleContext(), limit=10, cursor=None
    )
    assert "book" not in {item.facets["type"] for item in page.items}  # the page alone missed it
    suggested = await provider.suggestions(query, Principal(user_id=people["zoe"]))
    assert [item.facets["type"] for item in suggested] == ["game", "movie", "book", "game", "movie"]
