"""Spec 032 — a household profile restricted to an age is not served the films above it (nor, for a child,
the unrated ones): not in the catalog, locked on their page (with what « Ask for access » needs), not in the
media widgets' lists; its master's approval opens one title; unrated kinds (books) are never held back; the
master and members without restrictions see everything."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media import PORTAL_PLAYER
from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.modules.household.rules import RestrictionSettings
from portalab.modules.media.models import MediaObject, ObjectMetadata
from portalab.modules.media.restrictions import _scrub
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

RATINGS = {"Toy Story": "Tous publics", "Alien": "16", "Coco": "PG"}


def households(app: FastAPI) -> Any:
    """032: the household module's service (the households are no longer identity's)."""
    return app.state.household_module.service


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
    created = await households(app).create(
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
    assert problem["code"] == "household.restricted" and problem["rating"] == "16+"
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


async def test_locked_titles_show_and_requests_can_be_off(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "zoe")
    ids = await _library(app, media)
    owner = Principal(user_id=people["zoe"])
    lea = UUID(
        str(
            (await households(app).create(owner, display_name="Léa", kind="child", color=None, pin=None))[
                "id"
            ]
        )
    )
    await households(app).change(
        owner,
        lea,
        restrictions=RestrictionSettings(max_age=12, allow_unrated=True, mode="lock", requests=False),
    )
    await login(client, "zoe")
    await client.post("/api/v1/household/switch", json={"user_id": str(lea)})
    items = (await client.get("/api/v1/media", params={"kind": "movie"})).json()["items"]
    assert {i["title"]: i["locked"] for i in items} == {
        "Toy Story": False,
        "Alien": True,  # shown, locked: its master's choice
        "Coco": False,
        "Nameless": False,
    }
    locked = (await client.get(f"/api/v1/media/{ids['Alien']}")).json()
    assert locked["code"] == "household.restricted" and locked["can_ask"] is False
    assert locked["reason"] == "age"
    asked = await client.post("/api/v1/household/requests", json={"ref": str(ids["Alien"]), "title": "Alien"})
    assert asked.status_code == 403 and asked.json()["code"] == "household.requests_off"
    household = await client.get("/api/v1/media/insights", params={"scope": "household"})
    assert household.status_code == 200 and household.json()["scope"] == "me"  # its master's figures


async def test_a_profile_watches_with_its_master_account(app: FastAPI, media: MediaHarness) -> None:
    people = await users(app, media, "zoe")
    plex = media.service(1, "plex")
    await media.module.library.upsert(
        [library_record("m1", title="Alien", ids={"tmdb": "348"}, duration_s=6000)], plex
    )
    link = await media.module.links.claim(people["zoe"], plex.service_id, "zoe@plex")
    await media.module.links.verify(None, link.id, None)
    owner = Principal(user_id=people["zoe"])
    tom = UUID(
        str(
            (await households(app).create(owner, display_name="Tom", kind="standard", color=None, pin=None))[
                "id"
            ]
        )
    )
    assert await media.module.player._account(tom, plex.service_id) == "zoe@plex"  # its master's account

    # Tom starts a stream with the portal's player: the session the server reports is his
    await media.module.player._remember(tom, plex.service_id, "zoe@plex", "m1")
    fake = media.playback(plex)
    fake.play(
        "s1",
        external_user_id="zoe@plex",
        item_external_id="m1",
        kind="movie",
        duration_s=6000,
        device=PORTAL_PLAYER,
    )
    fake.play(
        "s2", external_user_id="zoe@plex", item_external_id="m1", kind="movie", duration_s=6000, device="TV"
    )
    await media.module.poller.poll(plex.service_id, fake)
    started = {p["session"].split(":")[-1]: who for _, p, who in await media.events("media.playback_started")}
    assert started == {"s1": str(tom), "s2": str(people["zoe"])}  # the living-room TV stays the master's


async def test_the_strictest_rating_and_kept_out_genres_hold(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "zoe")
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            library_record("s1", title="Smile", year=2022),
            library_record("n1", title="Nope", year=2022, genres=["Horreur"]),
            library_record("p1", title="Paddington", year=2014, content_rating="fr/TP"),
            library_record("x1", title="Saw", year=2004, content_rating="fr/-16"),
        ],
        one,
    )
    async with media.database.unit_of_work() as uow:
        ids = {t: i for t, i in (await uow.session.execute(select(MediaObject.title, MediaObject.id))).all()}
        for title, certifications in (
            ("Smile", {"FR": "12", "US": "R"}),
            ("Nope", {"FR": "TP", "US": "PG-13"}),
        ):
            uow.session.add(
                ObjectMetadata(
                    object_id=ids[title],
                    provider="tmdb",
                    status="found",
                    language="fr",
                    data={"certification": certifications["FR"], "certifications": certifications},
                    fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
            )
    owner = Principal(user_id=people["zoe"])
    created = await households(app).create(owner, display_name="Arthur", kind="child", color=None, pin=None)
    arthur = UUID(str(created["id"]))
    viewer = Principal(user_id=arthur, profile_of=people["zoe"])
    # 12 at most, unrated hidden, horror kept out: Smile (US R), Nope (horror), Saw (the server's 16) go
    assert await media.module.gate.blocked(viewer) == frozenset({ids["Smile"], ids["Nope"], ids["Saw"]})
    await households(app).change(
        owner, arthur, restrictions=RestrictionSettings(max_age=18, allow_unrated=True, genres=[])
    )
    media.module.gate.forget()
    assert await media.module.gate.blocked(viewer) == frozenset()

    await login(client, "zoe")
    smile = (await client.get(f"/api/v1/media/{ids['Smile']}")).json()["age_rating"]
    assert smile == {"age": 17, "ratings": [{"source": "FR", "value": "12"}, {"source": "US", "value": "R"}]}
    saw = (await client.get(f"/api/v1/media/{ids['Saw']}")).json()["age_rating"]
    assert saw == {"age": 16, "ratings": [{"source": "server", "value": "fr/-16"}]}


async def test_kinds_titles_and_screen_time(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    from portalab.modules.household.rules import KeptTitle
    from portalab.modules.media.insights.portal import PortalActivity
    from portalab.modules.media.restrictions import ScreenTimeUp

    people = await users(app, media, "zoe")
    ids = await _library(app, media)
    owner = Principal(user_id=people["zoe"])
    created = await households(app).create(owner, display_name="Léa", kind="standard", color=None, pin=None)
    lea = UUID(str(created["id"]))
    await households(app).change(
        owner,
        lea,
        restrictions=RestrictionSettings(
            types=["books"], titles=[KeptTitle(id=ids["Coco"], title="Coco")], daily_minutes=15
        ),
    )
    viewer = Principal(user_id=lea, profile_of=people["zoe"])
    assert await media.module.gate.blocked(viewer) == frozenset({ids["Coco"], ids["Le Petit Prince"]})
    assert await media.module.gate.screen_today(viewer) == (0, 15)
    from portalab.modules.media.restrictions import Restricted

    for title, reason in (("Coco", "title"), ("Le Petit Prince", "type")):
        with pytest.raises(Restricted) as kept:
            await media.module.gate.check(viewer, ids[title], title)
        assert kept.value.extensions["reason"] == reason and kept.value.extensions["can_ask"] is False
    await media.module.gate.check_screen(viewer)  # nothing watched yet

    await PortalActivity(media.database).store(
        ref="portal:t1",
        user=lea,
        service=media.service(1).service_id,
        object_id=ids["Toy Story"],
        kind="movie",
        watched=20 * 60,
        duration=None,
        share=None,
        ended=datetime.now(UTC),
    )
    assert await media.module.gate.screen_today(viewer) == (20, 15)
    with pytest.raises(ScreenTimeUp):
        await media.module.gate.check_screen(viewer)

    await login(client, "zoe")
    seen = await client.get("/api/v1/me/media/screen-time", params={"profile": str(lea)})
    assert seen.json() == {"used": 20, "allowed": 15}  # its master sees it
    assert (await client.get("/api/v1/me/media/screen-time")).json() is None  # the master has none


async def test_the_request_services_titles_follow_the_profile(app: FastAPI, media: MediaHarness) -> None:
    people = await users(app, media, "zoe")
    ids = await _library(app, media)
    owner = Principal(user_id=people["zoe"])
    created = await households(app).create(owner, display_name="Léa", kind="child", color=None, pin=None)
    lea = UUID(str(created["id"]))
    viewer = Principal(user_id=lea, profile_of=people["zoe"])
    items = [
        {"tmdb_id": "1", "kind": "movie", "title": "Alien", "object_id": str(ids["Alien"])},
        {"tmdb_id": "2", "kind": "movie", "title": "Toy Story", "object_id": str(ids["Toy Story"])},
        {"tmdb_id": "3", "kind": "movie", "title": "Outside", "object_id": None},  # no known rating
    ]
    assert [i["title"] for i in await media.module.gate.requestable(viewer, items)] == ["Toy Story"]
    await households(app).change(
        owner, lea, restrictions=RestrictionSettings(max_age=12, allow_unrated=True, mode="lock")
    )
    media.module.gate.forget()
    shown = await media.module.gate.requestable(viewer, items)
    assert [(i["title"], i.get("locked", False)) for i in shown] == [
        ("Alien", True),
        ("Toy Story", False),
        ("Outside", False),  # unrated titles allowed: kept
    ]
    assert await media.module.gate.requestable(owner, items) == items  # the master sees them all


async def test_a_rated_game_is_held_to_the_profiles_age(app: FastAPI, media: MediaHarness) -> None:
    """Issue 421: a game rated above a child's limit (PEGI, ESRB… from IGDB, through RomM) is kept from it;
    an unrated game — most retro games are older than the boards — stays open."""
    people = await users(app, media, "zoe")
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            library_record("g1", kind="game", title="Doom", content_rating="PEGI 18"),
            library_record("g2", kind="game", title="Mario", content_rating="PEGI 3"),
            library_record("g3", kind="game", title="Pong"),
        ],
        one,
    )
    async with media.database.session() as session:
        ids = {t: i for t, i in (await session.execute(select(MediaObject.title, MediaObject.id))).all()}
    owner = Principal(user_id=people["zoe"])
    created = await households(app).create(owner, display_name="Léa", kind="child", color=None, pin=None)
    viewer = Principal(user_id=UUID(str(created["id"])), profile_of=people["zoe"])
    assert await media.module.gate.blocked(viewer) == frozenset({ids["Doom"]})
    assert (await media.module.gate.rating(ids["Doom"]))["age"] == 18


async def test_every_card_carries_its_age_rating(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    """Issue 434: the catalog's cards carry their age rating (the strictest), for everyone — its badge."""
    await users(app, media, "zoe")
    await _library(app, media)
    await login(client, "zoe")
    items = (await client.get("/api/v1/media", params={"kind": "movie"})).json()["items"]
    ages = {item["title"]: item["age"] for item in items}
    assert ages["Alien"] == 16 and ages["Toy Story"] == 0 and ages["Nameless"] is None
