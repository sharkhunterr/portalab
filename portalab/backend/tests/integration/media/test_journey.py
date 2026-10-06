"""027 — a title's request journey: asked (by me), approved, released, searched by the download manager,
downloading (the torrent client tells it is stalled), waiting for a manual import, then available; the
interactive search runs on demand and is kept a while."""

from datetime import timedelta

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media import (
    ACQUISITION,
    DOWNLOAD_CLIENTS,
    DOWNLOADS,
    AcquisitionEvent,
    FoundRelease,
    SourceAcquisition,
    SourceDownload,
    TorrentState,
)
from portalab.capabilities.media.testkit import library_record
from portalab.core.time import FixedClock
from portalab.modules.media.models import MediaObject, UserLink
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users
from tests.integration.media.test_request_insights import _request

HASH = "b" * 40


class _Radarr:
    def __init__(self, clock: FixedClock) -> None:
        self.clock = clock
        self.has_file = False
        self.searches = 0

    async def status(self, kind: str, ids: dict[str, str]) -> SourceAcquisition | None:
        if ids.get("tmdb") != "949":
            return None
        now = self.clock.now()
        return SourceAcquisition(
            service_name="Radarr",
            tracked=True,
            monitored=True,
            has_file=self.has_file,
            status="released",
            searchable=True,
            releases={"cinema": now - timedelta(days=200), "digital": now - timedelta(days=100)},
            files=1 if self.has_file else 0,
            expected=1,
            link="http://radarr/movie/heat",
            history=(AcquisitionEvent("grabbed", now - timedelta(hours=3), "Heat.1995.1080p", "qBit"),),
        )

    async def search(self, kind: str, ids: dict[str, str]) -> list[FoundRelease]:
        self.searches += 1
        return [FoundRelease("Heat.1995.2160p", "Indexer", 40_000, "Bluray-2160p", 0, False, ("No seeders",))]


class _Queue:
    def __init__(self) -> None:
        self.items: list[SourceDownload] = []

    async def queue(self) -> list[SourceDownload]:
        return self.items


class _Client:
    async def torrents(self, hashes: list[str]) -> list[TorrentState]:
        return (
            [TorrentState(HASH, "Heat", "stalled", 0.4, 0, 0, None, 0, 4, "qBit")] if HASH in hashes else []
        )


async def test_journey(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe")
    library, seerr = media.service(1), media.service(8, "seerr")
    media.library(library)
    await media.module.library.upsert(
        [library_record("h", title="Heat", ids={"tmdb": "949"}, available=False)], library
    )
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            UserLink(
                user_id=people["zoe"],
                service_id=seerr.service_id,
                external_user_id="7",
                verified=True,
                created_at=clock.now(),
            )
        )
    await media.module.request_sink.upsert([_request(clock, "2", "Heat", "949", "processing", "7")], seerr)
    radarr, queue = _Radarr(clock), _Queue()
    media.provide(ACQUISITION, media.service(4, "radarr"), radarr)
    media.provide(DOWNLOADS, media.service(4, "radarr"), queue)
    media.provide(DOWNLOAD_CLIENTS, media.service(6, "qbittorrent"), _Client())
    async with media.database.session() as session:
        heat = await session.scalar(select(MediaObject.id).where(MediaObject.title == "Heat"))

    await login(client, "zoe")
    path = f"/api/v1/media/{heat}/journey"
    body = (await client.get(path)).json()
    steps = {s["key"]: s for s in body["steps"]}
    assert [s["key"] for s in body["steps"]] == [
        "requested",
        "approved",
        "released",
        "searched",
        "downloading",
        "imported",
        "available",
    ]
    assert steps["requested"]["by"] == {"me": True} and steps["approved"]["status"] == "done"
    assert steps["released"]["status"] == "done"
    assert steps["searched"] == {
        "key": "searched",
        "status": "current",
        "detail": "no_release",
        "manager": "Radarr",
    }
    assert body["manager"]["link"] == "http://radarr/movie/heat" and body["can_search"] is True

    queue.items = [
        SourceDownload(
            "q1", "movie", "Heat", "downloading", 0.4, ids={"tmdb": "949"}, download_id=HASH, client="qBit"
        )
    ]
    media.module.request_insights._queue = None  # the managers' queues are cached 30 s
    steps = {s["key"]: s for s in (await client.get(path)).json()["steps"]}
    downloading = steps["downloading"]
    assert downloading["status"] == "current" and downloading["items"][0]["torrent"]["state"] == "stalled"
    assert downloading["items"][0]["torrent"]["peers"] == 4

    queue.items = [
        SourceDownload(
            "q1",
            "movie",
            "Heat",
            "importing",
            1.0,
            ids={"tmdb": "949"},
            attention="import_blocked",
            messages=("No files found are eligible for import",),
        )
    ]
    media.module.request_insights._queue = None
    steps = {s["key"]: s for s in (await client.get(path)).json()["steps"]}
    assert steps["imported"]["status"] == "blocked" and steps["imported"]["detail"] == "manual"
    assert steps["imported"]["items"][0]["messages"] == ["No files found are eligible for import"]

    found = (await client.post(f"{path}/search")).json()
    again = (await client.post(f"{path}/search")).json()
    assert found["releases"][0]["rejections"] == ["No seeders"] and again == found and radarr.searches == 1

    queue.items, radarr.has_file = [], True
    media.module.request_insights._queue = None
    final = (await client.get(path)).json()
    assert final["available"] and final["steps"][-1]["status"] == "done" and final["can_search"] is False
    assert all(s["status"] == "done" for s in final["steps"])
