"""Spec 032 — a household profile restricted to an age is not served the films above it (nor, for a child,
the unrated ones): not in the catalog, locked on their page (with what « Ask for access » needs), not in the
media widgets' lists; its master's approval opens one title; unrated kinds (books) are never held back; the
master and members without restrictions see everything."""

from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.modules.media.models import MediaObject, ObjectMetadata
from portalab.modules.media.restrictions import _scrub
from tests.integration.identity.helpers import login, module_of
from tests.integration.media.conftest import MediaHarness, users

RATINGS = {"Toy Story": "Tous publics", "Alien": "16", "Coco": "PG"}


async def _library(app: FastAPI, media: MediaHarness) -> dict[str, UUID]:
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            library_record("m1", title="Toy Story", year=1995),
            library_record("m2", title="Alien", year=1979),
            library_record("m3", title="Coco", year=2017),
            library_record("m4", title="Nameless", year=2001),  # never enriched: unrated
            library_record("b1", kind="book", title="Le Petit Prince"),
        ],
        one,
    )
    async with media.database.unit_of_work() as uow:
        rows = (await uow.session.execute(select(MediaObject.title, MediaObject.id))).all()
        ids = {title: object_id for title, object_id in rows}
        for title, rating in RATINGS.items():
            uow.session.add(
                ObjectMetadata(
                    object_id=ids[title],
                    provider="tmdb",
                    status="found",
                    language="fr",
                    data={"certification": rating},
                    fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
            )
    return ids


async def _titles(client: httpx.AsyncClient, kind: str = "movie") -> set[str]:
    response = await client.get("/api/v1/media", params={"kind": kind})
    assert response.status_code == 200, response.text
    return {item["title"] for item in response.json()["items"]}


async def test_a_child_profile_sees_its_age_only(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "zoe")
    ids = await _library(app, media)
    identity = module_of(app)
    created = await identity.household.create(
        Principal(user_id=people["zoe"]), display_name="Léa", kind="child", color=None, pin=None
    )
    lea = UUID(str(created["id"]))
    await login(client, "zoe")
    assert await _titles(client) == {"Toy Story", "Alien", "Coco", "Nameless"}  # the master sees everything

    assert (await client.post("/api/v1/household/switch", json={"user_id": str(lea)})).status_code == 200
    assert await _titles(client) == {"Toy Story", "Coco"}  # 12 at most, rated titles only
    assert await _titles(client, "book") == {"Le Petit Prince"}  # books carry no rating
    locked = await client.get(f"/api/v1/media/{ids['Alien']}")
    assert locked.status_code == 403
    problem = locked.json()
    assert problem["code"] == "household.restricted" and problem["rating"] == "16"
    assert problem["object_id"] == str(ids["Alien"])
    assert (await client.get(f"/api/v1/media/{ids['Coco']}")).status_code == 200
    started = await client.get(f"/api/v1/media/{ids['Alien']}/player")
    assert started.status_code == 403

    asked = await client.post(
        "/api/v1/household/requests", json={"ref": str(ids["Alien"]), "title": "Alien", "rating": "16"}
    )
    request_id = asked.json()["id"]
    await client.post("/api/v1/household/switch", json={"user_id": str(people["zoe"])})
    decided = await client.post(f"/api/v1/household/requests/{request_id}/decision", json={"approve": True})
    assert decided.status_code == 204
    media.module.gate.forget()
    await client.post("/api/v1/household/switch", json={"user_id": str(lea)})
    assert await _titles(client) == {"Toy Story", "Coco", "Alien"}  # the master opened this one
    assert (await client.get(f"/api/v1/media/{ids['Alien']}")).status_code == 200

    blocked = await media.module.gate.blocked(Principal(user_id=lea, profile_of=people["zoe"]))
    assert blocked == frozenset({ids["Nameless"]})
    assert await media.module.gate.blocked(Principal(user_id=people["zoe"])) == frozenset()


def test_scrub_leaves_out_the_listed_titles_only() -> None:
    hidden = "0190a6d2-0000-7000-8000-000000000001"
    payload = {
        "items": [{"id": hidden, "title": "Alien"}, {"id": "other", "title": "Coco"}],
        "rows": [[{"object_id": hidden}], {"nested": [{"media_id": hidden}, 3]}],
        "id": hidden,  # a title's own page is not a list entry: left to the page's own check
    }
    assert _scrub(payload, {hidden}) == {
        "items": [{"id": "other", "title": "Coco"}],
        "rows": [[], {"nested": [3]}],
        "id": hidden,
    }
