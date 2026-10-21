"""Issue 184 — requests to the radio's DJ: a few free ones each day, then a credit bought in the shop per
request (once per purchase), refused when none is left; a request the station refuses does not count.
Through the HTTP API, with the member's allowance in the radio's state."""

from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.media import RADIO, RadioRequest, RadioState
from portalab.capabilities.media_core import RADIO_CREDITS
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

pytestmark = pytest.mark.integration


class _Station:
    def __init__(self) -> None:
        self.refuse = False

    async def state(self) -> RadioState:
        return RadioState(station="Retro Rock", on_air=True)

    async def ask(self, text: str, name: str) -> RadioRequest:
        return (
            RadioRequest(id=None, status="failed", detail="busy")
            if self.refuse
            else RadioRequest(id="r", status="pending")
        )

    async def request_status(self, request_id: str) -> RadioRequest:
        return RadioRequest(id=request_id, status="queued")

    def listen(self):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def cover(self, cover_ref: str) -> bytes:
        return b""


async def test_free_requests_then_credits(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "uma")
    station = _Station()
    media.module.capabilities.provide(RADIO, station, instance_ref="test", owner="test")
    media.module.config = replace(media.module.config, radio_free_requests_per_day=1)
    media.module.radio._asked.clear()
    await login(client, "uma")

    state = (await client.get("/api/v1/media/radio")).json()
    assert state["allowance"] == {"free_per_day": 1, "free_left": 1, "credits": 0}

    station.refuse = True  # refused by the station: given back
    assert (await client.post("/api/v1/media/radio/requests", json={"text": "x"})).json()[
        "status"
    ] == "failed"
    media.module.radio._asked.clear()
    station.refuse = False
    asked = (await client.post("/api/v1/media/radio/requests", json={"text": "M83"})).json()
    assert asked["status"] == "pending" and asked["allowance"]["free_left"] == 0
    media.module.radio._asked.clear()
    refused = await client.post("/api/v1/media/radio/requests", json={"text": "again"})
    assert refused.status_code == 429 and refused.json()["code"] == "media.radio_no_credits"

    credits = media.module.capabilities.system_providers(RADIO_CREDITS)[0].provider
    assert await credits.grant(people["uma"], 2, "marketplace:o1") == 2
    assert await credits.grant(people["uma"], 2, "marketplace:o1") == 2  # the same purchase again
    asked = (await client.post("/api/v1/media/radio/requests", json={"text": "Air"})).json()
    assert asked["allowance"] == {"free_per_day": 1, "free_left": 0, "credits": 1}
