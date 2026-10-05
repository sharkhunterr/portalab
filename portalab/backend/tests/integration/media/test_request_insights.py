"""027 — « My requests », after Telemetra: the funnel, kinds and timeline of my requests, how many I watched,
my anonymous rank among requesters, what is coming soon (downloading / importing with progress, release
dates) — and the configurable « recently requested » and « coming soon » widgets."""

from datetime import timedelta
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.media import CALENDAR, DOWNLOADS, SourceDownload, SourceRelease
from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock
from portalab.modules.media.models import Activity, MediaObject, ObjectMetadata, UserLink
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users


def _request(
    clock: FixedClock,
    external_id: str,
    title: str,
    tmdb: str,
    state: str,
    requester: str,
    kind: str = "movie",
) -> SourceRecord:
    return SourceRecord(
        source_system="seerr",
        external_id=external_id,
        kind="request",
        payload={
            "title": title,
            "kind": kind,
            "ids": {"tmdb": tmdb},
            "state": state,
            "requester": requester,
            **(
                {"available_at": (clock.now() + timedelta(hours=2)).isoformat()}
                if state == "available"
                else {}
            ),
        },
        observed_at=clock.now(),
    )


class _Queue:
    async def queue(self) -> list[SourceDownload]:
        return [SourceDownload("q1", "movie", "Heat", "downloading", 0.4, ids={"tmdb": "949"})]


class _Calendar:
    async def upcoming(self, start: Any, end: Any) -> list[SourceRelease]:
        return [
            SourceRelease(
                "m", "movie", "Arrival", start + timedelta(days=5), "digital", ids={"tmdb": "329865"}
            )
        ]


async def test_my_requests_page_and_widgets(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe", "max")
    library, seerr = media.service(1), media.service(8, "seerr")
    media.library(library)
    await media.module.library.upsert(
        [
            library_record("d", title="Dune", ids={"tmdb": "438631"}, genres=["Sci-Fi"]),
            library_record("h", title="Heat", ids={"tmdb": "949"}, available=False),
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
            _request(clock, "2", "Heat", "949", "processing", "7"),
            _request(clock, "3", "Arrival", "329865", "approved", "7"),
            _request(clock, "4", "Andor", "83867", "pending", "7", kind="series"),
            _request(clock, "5", "Alien", "348", "declined", "8"),
        ],
        seerr,
    )
    media.provide(DOWNLOADS, media.service(4, "radarr"), _Queue())
    media.provide(CALENDAR, media.service(5, "radarr"), _Calendar())
    async with media.database.session() as session:
        dune = await session.scalar(select(MediaObject.id).where(MediaObject.title == "Dune"))
    async with media.database.unit_of_work() as uow:  # TMDB knows when Dune came out
        uow.session.add(
            ObjectMetadata(
                object_id=dune,
                provider="tmdb",
                status="found",
                language="en",
                data={"release_date": "2021-09-15"},
                fetched_at=clock.now(),
            )
        )
    async with media.database.unit_of_work() as uow:  # Zoé watched one of her requests
        uow.session.add(
            Activity(
                service_id=library.service_id,
                ref="p1",
                family=None,
                priority=10,
                counted=True,
                external_user_id="z",
                user_id=people["zoe"],
                kind="movie",
                title="Dune",
                object_id=dune,
                work_id=dune,
                ids={},
                started_at=clock.now(),
                watched_s=3600,
                received_at=clock.now(),
            )
        )

    await login(client, "zoe")
    data = (await client.get("/api/v1/me/media/requests/insights", params={"period": "30d"})).json()
    assert data["summary"] == {"total": 4, "pending": 1, "approved": 2, "available": 1, "declined": 0}
    assert data["by_kind"] == {"movie": 3, "series": 1}
    assert data["watched"] == {"requested": 4, "watched": 1, "rate": 0.25}
    assert (
        data["ranking"]["position"] == 1 and data["ranking"]["total"] == 2 and data["ranking"]["count"] == 4
    )
    assert sum(p["count"] for p in data["timeline"]["points"]) == 4 and "quota" in data
    assert data["genres"]["requested"] == [{"name": "Sci-Fi", "value": 1}]
    acquisition = data["acquisition"]  # Dune: asked years after release, available 2 hours later
    assert {b["key"]: b["count"] for b in acquisition["buckets"]}["day"] == 1
    assert acquisition["median_hours"] == 2 and acquisition["pending"] == 3
    first = acquisition["points"][0]
    assert first["moment"] == "catalog" and first["asked_after_days"] > 365
    assert data["top_watched"][0]["title"] == "Dune" and data["top_watched"][0]["route"] == f"/media/{dune}"

    listed = (await client.get("/api/v1/me/media/requests/list")).json()["items"]
    assert [i["title"] for i in listed][:1] and {i["state"] for i in listed} == {
        "available",
        "processing",
        "approved",
        "pending",
    }
    soon = (await client.get("/api/v1/me/media/requests/soon")).json()["items"]
    assert [(i["title"], i["phase"]) for i in soon] == [("Heat", "downloading"), ("Arrival", "release")]
    assert soon[0]["progress"] == 0.4 and soon[1]["release_type"] == "digital"

    zoe, ctx = Principal(user_id=people["zoe"]), LocaleContext()
    widget = media.widgets.get("media.my_soon")
    assert widget is not None and widget.definition.required_permission == "media.request"
    mine = await widget.provider.load(zoe, {}, ctx)
    assert [i["phase"] for i in mine.data["items"]] == ["downloading", "release"]
    recent = media.widgets.get("media.recently_requested")
    assert recent is not None
    everyone = await recent.provider.load(zoe, {}, ctx)
    assert len(everyone.data["items"]) == 5
    series_only = await recent.provider.load(zoe, {"scope": "me", "kind": "series"}, ctx)
    assert [i["title"] for i in series_only.data["items"]] == ["Andor"]
    declined = await recent.provider.load(zoe, {"state": "declined"}, ctx)
    assert [i["title"] for i in declined.data["items"]] == ["Alien"]
