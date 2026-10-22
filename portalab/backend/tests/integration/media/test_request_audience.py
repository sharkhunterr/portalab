"""issue 222 — the audience of requests in « My requests »: how many other members watched my requests (a
number, never who; the requester's own plays and plays before the request do not count), which of them drew
the most, my rank by audience, the requesters' podiums — and the deeper parts sold in the shop."""

from datetime import timedelta
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media.testkit import library_record
from portalab.core.time import FixedClock
from portalab.modules.media.models import Activity, MediaObject, UserLink
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users
from tests.integration.media.test_request_insights import _request
from tests.integration.media.test_sold_statistics import _shop


def _play(service: UUID, work: UUID, account: str, user: UUID | None, at: object, ref: str) -> Activity:
    return Activity(
        service_id=service,
        ref=ref,
        family=None,
        priority=10,
        counted=True,
        external_user_id=account,
        user_id=user,
        kind="movie",
        title="?",
        object_id=work,
        work_id=work,
        ids={},
        started_at=at,
        watched_s=3600,
        received_at=at,
    )


async def test_the_audience_of_my_requests(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe", "max", "lea")
    library, seerr = media.service(1), media.service(8, "seerr")
    media.library(library)
    await media.module.library.upsert(
        [
            library_record("d", title="Dune", ids={"tmdb": "438631"}, genres=["Sci-Fi"]),
            library_record("a", title="Alien", ids={"tmdb": "348"}, genres=["Horror", "Sci-Fi"]),
            library_record("h", title="Heat", ids={"tmdb": "949"}),
        ],
        library,
    )
    async with media.database.unit_of_work() as uow:
        for name, account in (("zoe", "7"), ("max", "8")):
            uow.session.add(
                UserLink(
                    user_id=people[name],
                    service_id=seerr.service_id,
                    external_user_id=account,
                    verified=True,
                    created_at=clock.now(),
                )
            )
    await media.module.request_sink.upsert(
        [
            _request(clock, "1", "Dune", "438631", "available", "7"),
            _request(clock, "2", "Heat", "949", "available", "7"),
            _request(clock, "3", "Alien", "348", "available", "8"),
        ],
        seerr,
    )
    async with media.database.session() as session:
        found = dict((await session.execute(select(MediaObject.title, MediaObject.id))).all())
    dune, alien, heat = found["Dune"], found["Alien"], found["Heat"]
    later, before = clock.now() + timedelta(hours=3), clock.now() - timedelta(days=2)
    service = library.service_id
    async with media.database.unit_of_work() as uow:
        uow.session.add_all(
            [
                _play(service, dune, "m", people["max"], later, "1"),  # Max twice: one viewer, two plays
                _play(service, dune, "m", people["max"], later + timedelta(hours=1), "2"),
                _play(service, dune, "l", people["lea"], later, "3"),
                _play(service, dune, "x", None, later, "4"),  # a media server's own account
                _play(service, dune, "z", people["zoe"], later, "5"),  # her own play: not her audience
                _play(service, heat, "l", people["lea"], later, "6"),
                _play(service, heat, "m", people["max"], before, "7"),  # before the request: not counted
                _play(service, alien, "l", people["lea"], later, "8"),
            ]
        )

    await login(client, "zoe")
    data = (await client.get("/api/v1/me/media/requests/insights", params={"period": "30d"})).json()
    # Dune: Max, Léa and the server's account; Heat: Léa again — three different viewers, five plays
    assert data["audience"] == {"requested": 2, "seen": 2, "viewers": 3, "plays": 5}
    titles = data["audience_titles"]
    assert [(t["title"], t["viewers"], t["plays"]) for t in titles["items"]] == [
        ("Dune", 3, 4),
        ("Heat", 1, 1),
    ]
    assert titles["position"] == 1 and titles["total"] == 2
    leaders = data["leaders"]
    assert [(e["rank"], e["me"], e["value"]) for e in leaders["requests"]] == [(1, True, 2), (2, False, 1)]
    assert [(e["rank"], e["me"], e["value"]) for e in leaders["viewers"]] == [(1, True, 4), (2, False, 1)]
    assert leaders["per_request"] == []  # nobody asked three titles yet
    assert all(e["name"] is None for e in leaders["requests"] if e["me"])
    assert "max" not in str(titles) and str(people["max"]) not in str(data)  # never who watched

    depth = data["audience_depth"]  # both arrived 2 hours after the request; first watched an hour later
    reactivity = depth["reactivity"]
    assert reactivity["median_hours"] == 1 and reactivity["waiting"] == 0
    assert {b["key"]: b["count"] for b in reactivity["buckets"]}["hour"] == 2
    assert depth["genres"]["mine"] == [{"name": "Sci-Fi", "viewers": 3, "requests": 1}]
    assert depth["genres"]["server"] == [
        {"name": "Sci-Fi", "viewers": 4, "requests": 2},
        {"name": "Horror", "viewers": 1, "requests": 1},
    ]
    assert depth["kinds"]["movie"] == {
        "requests": 2,
        "plays": 5,
        "available": 2,
        "seen_rate": 1.0,
        "viewers_per_request": 2.0,
    }
    assert depth["versus"]["server"]["viewers_per_request"] == 1.67 and depth["late_share"] == 0
    assert sum(p["plays"] for p in depth["over_time"]["points"]) == 5

    shop = _shop(media)  # the deeper parts are sold: left out until bought, the totals stay free
    data = (await client.get("/api/v1/me/media/requests/insights", params={"period": "30d"})).json()
    assert data["audience"]["viewers"] == 3
    assert data["audience_titles"] is None and data["leaders"] is None and data["audience_depth"] is None
    assert {"audience_titles", "leaders", "audience_depth"} <= set(data["locked"])
    shop.owned_by[people["zoe"]] = frozenset({"media.requests.leaders"})
    data = (await client.get("/api/v1/me/media/requests/insights", params={"period": "30d"})).json()
    assert data["leaders"] is not None and data["audience_titles"] is None
