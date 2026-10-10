"""061 — more of the statistics sold: the tabs in depth, the long history, the whole server's view and the
deeper statistics of « My requests » are refused or left out until bought; the minimum (overview, periods up
to a year, my requests' funnel) stays free; media managers have everything."""

from contextlib import suppress
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI

from portalab.capabilities.themes import COSMETICS, COSMETICS_SPEC
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

SOLD = frozenset(
    {
        "media.insights.tab.casting",
        "media.insights.history",
        "media.insights.server",
        "media.requests.ranking",
        "media.requests.genres",
    }
)


class _Shop:
    def __init__(self) -> None:
        self.owned_by: dict[UUID, frozenset[str]] = {}

    async def sold(self, kind: str, field: str) -> frozenset[str]:
        return SOLD if (kind, field) == ("statistic", "statistic") else frozenset()

    async def owned(self, user_id: UUID, kind: str, field: str) -> frozenset[str]:
        return self.owned_by.get(user_id, frozenset())

    async def equipped(self, user_id: UUID) -> dict[str, Any]:
        return {}


def _shop(media: MediaHarness) -> _Shop:
    shop = _Shop()
    capabilities = media.module.capabilities
    with suppress(Exception):  # already declared by the harness
        capabilities.declare(COSMETICS_SPEC)
    capabilities.provide(COSMETICS, shop, instance_ref="shop", owner="test")
    return shop


async def test_sold_statistics_are_locked_until_bought(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "zoe", admin="boss")
    shop = _shop(media)
    await login(client, "zoe")
    locked = (await client.get("/api/v1/me/media/insights/locked")).json()["locked"]
    assert set(locked) == SOLD

    assert (await client.get("/api/v1/media/insights?period=365d")).status_code == 200  # free minimum
    refused = await client.get("/api/v1/media/insights?period=all")
    assert refused.status_code == 403 and refused.json()["code"] == "media.statistic_locked"
    assert (await client.get("/api/v1/media/insights?period=2025")).status_code == 403
    assert (await client.get("/api/v1/media/insights?scope=all")).status_code == 403
    assert (await client.get("/api/v1/media/insights/casting")).status_code == 403
    assert (await client.get("/api/v1/media/insights/production")).status_code == 200  # not on sale

    mine = (await client.get("/api/v1/me/media/requests/insights")).json()
    assert mine["locked"] == ["genres", "ranking"]
    assert mine["ranking"] is None and mine["genres"] is None and mine["summary"]["total"] == 0

    shop.owned_by[people["zoe"]] = frozenset({"media.insights.history", "media.insights.tab.casting"})
    assert (await client.get("/api/v1/media/insights?period=all")).status_code == 200
    assert (await client.get("/api/v1/media/insights/casting")).status_code == 200
    locked = (await client.get("/api/v1/me/media/insights/locked")).json()["locked"]
    assert "media.insights.history" not in locked and "media.insights.server" in locked

    await login(client, "boss")  # a media manager has every statistic
    assert (await client.get("/api/v1/me/media/insights/locked")).json()["locked"] == []
    assert (await client.get("/api/v1/media/insights?scope=all&period=all")).status_code == 200
