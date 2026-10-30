"""#283 — the radio in the statistics, and only the tabs a configured service feeds: the radio's sittings,
once over, count (in « all » and a Radio tab of their own, once, already rewarded); a tab shows when a
connected service's catalog or history holds its kind, the radio's when a station is connected, the requests'
when a request service is."""

from datetime import timedelta
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media import RADIO, REQUESTS, RadioRequest, RadioState
from portalab.capabilities.media.testkit import FakeLibrary, FakeRequests, library_record
from portalab.core.time import FixedClock
from portalab.modules.media.models import Activity
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users


class _Station:
    async def state(self) -> RadioState:
        return RadioState(station="SUB/WAVE", on_air=True)

    async def ask(self, text: str, name: str) -> RadioRequest:
        return RadioRequest(id="r1", status="pending")

    async def request_status(self, request_id: str) -> RadioRequest:
        return RadioRequest(id=request_id, status="queued")

    def listen(self):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def cover(self, cover_ref: str) -> bytes:
        return b""


async def _tabs(client: httpx.AsyncClient) -> list[str]:
    answer = await client.get("/api/v1/media/insights/categories")
    assert answer.status_code == 200, answer.text
    return list(answer.json()["categories"])


async def test_radio_counts_and_tabs_follow_the_services(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    ivy: UUID = (await users(app, media, "ivy"))["ivy"]
    await login(client, "ivy")
    assert await _tabs(client) == ["all"]  # nothing connected: nothing to show but the whole

    plex, grimmory = media.service(1), media.service(2)
    media.library(plex)
    media.provide("media.library", grimmory, FakeLibrary())
    await media.module.library.upsert([library_record("m1", title="Dune", kind="movie", year=2021)], plex)
    await media.module.library.upsert(
        [library_record("a1", title="Alien", kind="audiobook", year=2026)], grimmory
    )
    assert await _tabs(client) == ["all", "movies", "audiobooks"]

    station = media.service(3)
    media.provide(RADIO, station, _Station())
    media.provide(REQUESTS, media.service(4), FakeRequests())
    assert await _tabs(client) == ["all", "movies", "audiobooks", "radio", "requests"]

    radio = media.module.radio
    await radio.heard(ivy, 1200)
    await radio.heard(ivy, 30)  # within the same sitting
    clock.advance(timedelta(minutes=11))
    assert await radio.sweep() == 1
    await radio.heard(ivy, 40)  # a sitting under a minute is no listening
    clock.advance(timedelta(minutes=11))
    assert await radio.sweep() == 1

    await media.module.ingestor.run()
    await media.module.ingestor.run()  # once
    async with media.database.session() as session:
        rows = list((await session.execute(select(Activity).where(Activity.kind == "radio"))).scalars())
    assert len(rows) == 1
    sitting = rows[0]
    assert sitting.user_id == ivy and sitting.service_id == station.service_id and sitting.title == "SUB/WAVE"
    assert sitting.watched_s == 1230 and sitting.rewarded_at is not None

    while await media.module.aggregator.run():
        pass
    tab = (await client.get("/api/v1/media/insights", params={"category": "radio"})).json()
    assert tab["category"] == "radio" and tab["totals"]["seconds"] == 1230 and tab["totals"]["plays"] == 1
    whole = (await client.get("/api/v1/media/insights")).json()
    assert {k["kind"] for k in whole["by_kind"]} == {"radio"}
    games = await client.get("/api/v1/media/insights", params={"category": "games"})
    assert games.status_code == 200 and games.json()["totals"]["plays"] == 0
