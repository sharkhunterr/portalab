"""008 T012 — ``POST /search`` returns groups with per-group state and facets without any AI; filters
change results; cursor pagination; typos and accents matched; rate limit 429; length cap 422."""

from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI

from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.search.conftest import SearchHarness

pytestmark = pytest.mark.integration


async def signed_in(app: FastAPI, client: httpx.AsyncClient, name: str = "alex") -> None:
    await create_user(module_of(app), name)
    assert (await login(client, name)).status_code == 200


async def test_grouped_results_without_ai(
    app: FastAPI, client: httpx.AsyncClient, search: SearchHarness
) -> None:
    await create_user(module_of(app), "elodie", display_name="Élodie Durand")
    await signed_in(app, client)
    body = (await client.post("/api/v1/search", json={"q": "elodie"})).json()
    groups = {g["kind"]: g for g in body["groups"]}
    assert set(groups) == {"navigation", "services", "users", "media"}
    assert all(g["state"] == "ok" for g in groups.values())
    [hit] = groups["users"]["items"]
    assert hit["title"] == "Élodie Durand" and hit["url_ref"].startswith("/users/")
    assert any(s["hit"] and s["text"] == "Élodie" for s in hit["snippet"])
    assert body["semantic"] == "unavailable"  # no embedding provider: said honestly
    typo = (await client.post("/api/v1/search", json={"q": "Duramd", "kinds": ["users"]})).json()
    assert [i["title"] for i in typo["groups"][0]["items"]] == ["Élodie Durand"]


async def test_filters_facets_and_pagination(
    app: FastAPI, client: httpx.AsyncClient, search: SearchHarness
) -> None:
    await signed_in(app, client)
    every = (await client.post("/api/v1/search", json={"q": "", "kinds": ["services"]})).json()
    [group] = every["groups"]
    assert len(group["items"]) == 2
    facets = {f["key"]: f["counts"] for f in group["facets"]}
    assert facets["state"] == {"enabled": 1, "error": 1}
    broken = (
        await client.post(
            "/api/v1/search", json={"q": "", "kinds": ["services"], "filters": {"state": ["error"]}}
        )
    ).json()
    assert [i["title"] for i in broken["groups"][0]["items"]] == ["Café Books"]
    inline = (await client.post("/api/v1/search", json={"q": "type:services state:enabled"})).json()
    assert [i["title"] for g in inline["groups"] for i in g["items"]] == ["Jellyfin Media"]
    search.module.config = replace(search.module.config, max_results_per_group=1)
    first = (await client.post("/api/v1/search", json={"q": "", "kinds": ["services"]})).json()["groups"][0]
    assert len(first["items"]) == 1 and first["next_cursor"]
    second = (
        await client.post(
            "/api/v1/search", json={"q": "", "kinds": ["services"], "cursor": first["next_cursor"]}
        )
    ).json()["groups"][0]
    assert second["items"][0]["id"] != first["items"][0]["id"] and second["next_cursor"] is None
    unknown = await client.post("/api/v1/search", json={"q": "x", "filters": {"colour": ["red"]}})
    assert unknown.status_code == 422 and unknown.json()["code"] == "search.invalid_filter"


async def test_accents_and_limits(app: FastAPI, client: httpx.AsyncClient, search: SearchHarness) -> None:
    await signed_in(app, client)
    cafe = (await client.post("/api/v1/search", json={"q": "cafe", "kinds": ["services"]})).json()
    assert [i["title"] for i in cafe["groups"][0]["items"]] == ["Café Books"]
    long = await client.post("/api/v1/search", json={"q": "x" * 300})
    assert long.status_code == 422 and long.json()["code"] == "search.query_too_long"
    search.module.config = replace(search.module.config, rate_limit_per_minute=2)
    statuses = [(await client.post("/api/v1/search", json={"q": "a"})).status_code for _ in range(3)]
    assert statuses[-1] == 429
    assert (await client.post("/api/v1/search", json={"q": "a"})).json()["code"] == "search.rate_limited"


async def test_unavailable_provider_keeps_others(
    app: FastAPI, client: httpx.AsyncClient, search: SearchHarness
) -> None:
    await signed_in(app, client)

    async def broken() -> list[object]:
        raise RuntimeError("directory down")

    search.directory.services = broken  # type: ignore[method-assign]
    body = (await client.post("/api/v1/search", json={"q": "status"})).json()
    states = {g["kind"]: g["state"] for g in body["groups"]}
    assert states["services"] == "unavailable" and states["navigation"] == "ok"
    assert [i["url_ref"] for g in body["groups"] if g["kind"] == "navigation" for i in g["items"]] == [
        "/services"
    ]


async def test_suggest(app: FastAPI, client: httpx.AsyncClient, search: SearchHarness) -> None:
    await signed_in(app, client)
    items = (await client.get("/api/v1/search/suggest", params={"q": "jelly"})).json()["items"]
    assert [i["title"] for i in items] == ["Jellyfin Media"]
    assert (await client.get("/api/v1/search/suggest")).json()["items"] == []
