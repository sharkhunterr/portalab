"""Issue 363, #378 — a book, an audiobook, a game… asked of the team as a film is asked of the request
service: the portal's own request (the same « My requests », queue, states and figures), refused when the
library has the title (by one of its identifiers, by its title and author), not asked twice; approved or
declined in the administrators' queue; there once the library has it (the member told); nothing asked of
the team while the module is switched off."""

from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.modules.media.models import ExternalId, MediaObject, MediaRequest
from portalab.modules.requests.models import TitleRequest
from portalab.modules.requests.module import RequestsModule
from portalab.modules.requests.service import TEAM
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

pytestmark = pytest.mark.integration


def _book(ref: str, title: str, author: str = "Robin Hobb") -> object:
    return library_record(ref, kind="book", title=title, authors=[author], people=[author])


async def _object(media: MediaHarness, title: str) -> UUID:
    async with media.database.session() as session:
        found: UUID = (
            await session.execute(select(MediaObject.id).where(MediaObject.title == title))
        ).scalar_one()
        return found


def test_the_team_s_service_is_the_migration_s() -> None:
    assert str(TEAM) == "71ab2125-cb76-5dcb-a322-778b0eb93b90"  # requests_0002 moved the requests under it


async def test_a_book_asked_as_a_film_is(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, team: RequestsModule
) -> None:
    people = await users(app, media, "zoe", "leo", admin="ann")
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert([_book("b1", "L'Apprenti assassin")], one)  # type: ignore[list-item]
    async with media.database.unit_of_work() as uow:
        first = await _object(media, "L'Apprenti assassin")
        uow.session.add(ExternalId(scheme="isbn", value="9782290302512", object_id=first))

    await login(client, "zoe")
    options = (await client.get("/api/v1/requests/options")).json()
    assert options["kinds"] == ["book", "audiobook", "game"] and "movie" not in options["known"]

    # the library has it: by its title and author, by one of its identifiers
    there = await client.post(
        "/api/v1/media/requests",
        json={"kind": "book", "title": "l'apprenti ASSASSIN", "creators": ["Robin Hobb"]},
    )
    assert there.status_code == 409 and there.json()["code"] == "media.request_in_library"
    assert there.json()["route"] == f"/media/{first}"
    by_id = await client.post(
        "/api/v1/media/requests",
        json={"kind": "book", "title": "Assassin's Apprentice", "ids": {"isbn": "9782290302512"}},
    )
    assert by_id.json()["code"] == "media.request_in_library"
    # a kind no request service takes
    album = await client.post("/api/v1/media/requests", json={"kind": "album", "title": "Abbey Road"})
    assert album.status_code == 503 and album.json()["code"] == "media.service_unavailable"

    asked = await client.post(
        "/api/v1/media/requests",
        json={
            "kind": "book",
            "title": "Le Prophète blanc",
            "creators": ["Robin Hobb"],
            "year": 2004,
            "details": {"language": "fr", "edition": "Read, J'ai Lu"},
            "ids": {"hardcover": "917"},
            "note": "Le tome 7",
            "cover": "/api/v1/media/book-covers?service=s&ref=%2Fc.jpg",
            "sheet": "/media/book?service=s&ref=917",
        },
    )
    assert asked.status_code == 201
    request = asked.json()
    assert request["state"] == "pending" and request["kind"] == "book" and request["service_id"] == str(TEAM)
    async with media.database.session() as session:
        kept = (await session.execute(select(TitleRequest))).scalar_one()
        assert (kept.title, kept.creators, kept.details, kept.note) == (
            "Le Prophète blanc",
            ["Robin Hobb"],
            {"language": "fr", "edition": "Read, J'ai Lu"},
            "Le tome 7",
        )

    # in « My requests », as a film is — its cover and sheet the request's own
    mine = (await client.get("/api/v1/me/media/requests/list")).json()["items"]
    assert [(i["title"], i["kind"], i["state"]) for i in mine] == [("Le Prophète blanc", "book", "pending")]
    assert mine[0]["cover"].startswith("/api/v1/media/book-covers") and mine[0]["sheet"].startswith(
        "/media/book"
    )

    # asked again by another member: already requested, as a film
    await login(client, "leo")
    again = await client.post(
        "/api/v1/media/requests",
        json={"kind": "book", "title": "le prophete blanc", "creators": ["robin hobb"]},
    )
    assert again.status_code == 409 and again.json()["code"] == "media.request_duplicate"

    # the administrators' queue, with the films': approved there, taken by the team
    await login(client, "ann")
    queue = (await client.get("/api/v1/admin/media/requests")).json()["items"]
    item = next(i for i in queue if i["id"] == request["id"])
    assert item["kind"] == "book" and item["decidable"] and item["requester"]["name"] == "zoe"
    approved = await client.post(f"/api/v1/admin/media/requests/{request['id']}/approve", json={})
    assert approved.json() == {"state": "approved"}
    async with media.database.session() as session:
        assert (await session.execute(select(TitleRequest.status))).scalar_one() == "accepted"

    # the library gets it: the request is there, its page given; the member told (the portal's event)
    await media.module.library.upsert(  # type: ignore[list-item]
        [_book("b1", "L'Apprenti assassin"), _book("b7", "Le Prophète blanc")], one
    )
    assert await team.team.sweep() == 1
    prophet = await _object(media, "Le Prophète blanc")
    async with media.database.session() as session:
        row = await session.get(MediaRequest, UUID(request["id"]))
        assert row is not None and row.state == "available" and row.object_id == prophet
    assert "media.request_available" in {t for t, _, _ in await media.events("media.request")}
    assert people["zoe"]

    # switched off from the module manager: nothing asked of the team
    await media.ev.full.administration.toggles.set(Principal(channel="system"), "module", "requests", False)
    assert (await client.get("/api/v1/requests/options")).status_code == 503


async def test_a_declined_request_and_the_figures(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, team: RequestsModule
) -> None:
    await users(app, media, "zoe", admin="ann")
    await login(client, "zoe")
    asked = (
        await client.post("/api/v1/media/requests", json={"kind": "game", "title": "Chrono Trigger"})
    ).json()
    await login(client, "ann")
    declined = await client.post(
        f"/api/v1/admin/media/requests/{asked['id']}/decline", json={"reason": "Pas de ROM"}
    )
    assert declined.json() == {"state": "declined"}
    async with media.database.session() as session:
        assert (await session.execute(select(TitleRequest.status))).scalar_one() == "refused"
    await login(client, "zoe")
    figures = (await client.get("/api/v1/me/media/requests")).json()
    assert figures is not None
    stats = (await client.get("/api/v1/me/media/requests/insights", params={"period": "all"})).json()
    assert stats["by_kind"]["game"] == 1 and stats["summary"]["total"] == 1  # the same figures as a film's
