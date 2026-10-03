"""017 T010/T015/T032 — personal statistics are owner-only (another user ⇒ 403 unless their visibility
allows); a community statistic below the cohort threshold is ``insufficient_data``; small dimension cells
are merged/suppressed so totals never reveal them; only ``statistics.manage`` authors definitions; users
cannot hide non-hideable statistics; route permissions."""

from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.privacy.conftest import NOW
from tests.integration.statistics.conftest import StatsHarness

pytestmark = pytest.mark.integration

PERSONAL = {
    "key": "media.my_minutes",
    "title_key": "t",
    "domain": "media",
    "scope": "personal",
    "event_types": ["media.played"],
    "measure": {"kind": "sum", "field": "minutes"},
    "hideable": False,
}
COMMUNITY = {
    "key": "media.by_genre",
    "title_key": "t",
    "domain": "media",
    "scope": "community",
    "event_types": ["media.played"],
    "measure": {"kind": "sum", "field": "minutes"},
    "dimensions": ["genre"],
}


async def play(stats: StatsHarness, actor: object, minutes: int, genre: str) -> None:
    await stats.publish(
        "media.played",
        {"minutes": minutes, "genre": genre, "service_id": "s1"},
        at=NOW - timedelta(hours=1),
        actor=actor,
    )  # type: ignore[arg-type]


async def test_personal_is_owner_only(app: FastAPI, client: httpx.AsyncClient, stats: StatsHarness) -> None:
    alex = await create_user(module_of(app), "alex")
    sam = await create_user(module_of(app), "sam")
    await play(stats, alex, 30, "rock")
    await stats.define(PERSONAL)
    await stats.dispatch()
    await login(client, "alex")
    mine = (
        await client.get("/api/v1/statistics/media.my_minutes", params={"period": "last_n_days", "days": 7})
    ).json()
    assert mine["state"] == "available" and mine["value"] == 30
    await login(client, "sam")
    assert (await client.get("/api/v1/statistics/media.my_minutes")).json()["value"] == 0
    other = await client.get("/api/v1/statistics/media.my_minutes", params={"subject": str(alex)})
    assert other.status_code == 403 and other.json()["code"] == "statistics.forbidden"
    refused = await client.put("/api/v1/me/statistics/preferences", json={"hidden": ["media.my_minutes"]})
    assert refused.status_code == 422 and refused.json()["code"] == "statistics.not_hideable"
    del sam


async def test_cohort_threshold_and_suppression(
    app: FastAPI, client: httpx.AsyncClient, stats: StatsHarness
) -> None:
    await stats.define(COMMUNITY)
    for _ in range(4):
        await play(stats, uuid4(), 10, "rock")
    await stats.dispatch()
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    few = (await client.get("/api/v1/statistics/media.by_genre")).json()
    assert few["state"] == "insufficient_data" and few["value"] is None and few["breakdown"] == []
    for _ in range(6):
        await play(stats, uuid4(), 10, "rock")
    await play(stats, uuid4(), 99, "jazz")  # a single jazz listener: must not be identifiable
    await stats.dispatch()
    enough = (await client.get("/api/v1/statistics/media.by_genre")).json()
    assert enough["state"] == "available" and enough["value"] == 199
    genres = {next(iter(c["dims"].values())) for c in enough["breakdown"]}
    assert (
        "jazz" not in genres
    )  # suppressed, and the only visible cell absorbed so 199 - visible reveals nothing
    assert sum(c["value"] for c in enough["breakdown"]) in (0, 199)


async def test_authorship_and_matrix(app: FastAPI, client: httpx.AsyncClient, stats: StatsHarness) -> None:
    routes = [
        ("GET", "/api/v1/statistics/catalog"),
        ("GET", "/api/v1/statistics/media.x"),
        ("GET", "/api/v1/me/statistics/preferences"),
        ("PUT", "/api/v1/me/statistics/preferences"),
        ("GET", "/api/v1/me/wrapped"),
        ("GET", "/api/v1/wrapped/community/2026-09-01"),
        ("GET", "/api/v1/admin/statistics/definitions"),
        ("POST", "/api/v1/admin/statistics/definitions"),
        ("POST", "/api/v1/admin/statistics/definitions/media.x/activate"),
        ("POST", "/api/v1/admin/statistics/definitions/media.x/rebuild"),
        ("GET", "/api/v1/admin/statistics/status"),
    ]
    for method, path in routes:
        assert (await client.request(method, path, json={})).status_code == 401, path
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    for method, path in routes[6:]:
        assert (await client.request(method, path, json={"definition": COMMUNITY})).status_code == 403, path
    boss = await create_user(module_of(app), "boss")
    await make_admin(stats.ev.full, boss)
    await login(client, "boss")
    bad = await client.post(
        "/api/v1/admin/statistics/definitions", json={"definition": {**COMMUNITY, "dimensions": ["artist"]}}
    )
    assert bad.status_code == 422 and bad.json()["code"] == "statistics.invalid_definition"
    created = await client.post("/api/v1/admin/statistics/definitions", json={"definition": COMMUNITY})
    assert created.json() == {"key": "media.by_genre", "version": 1}
    first = await client.post("/api/v1/admin/statistics/definitions/media.by_genre/activate", json={})
    assert first.status_code == 409 and first.json()["code"] == "authz.confirmation_required"
    token = first.json()["confirmation"]
    done = await client.post(
        "/api/v1/admin/statistics/definitions/media.by_genre/activate", json={"confirmation": token}
    )
    assert done.json() == {"key": "media.by_genre", "active_version": 1}
