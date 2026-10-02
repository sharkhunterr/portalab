"""008 T021/T034/T035 — no leakage: an ungranted domain contributes nothing (no group, count or facet);
permission changes apply on the next search; snippets carry plain text only; the AI receives only
references the principal may see (see test_assist_independence); no query text reaches events or logs;
route permissions of every search endpoint."""

import logging

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.modules.identity.domain.state_machine import AccountState
from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of, set_state
from tests.integration.search.conftest import SearchHarness
from tests.unit.search.fakes import FakeProvider

pytestmark = pytest.mark.integration

SECRET_QUERY = "zebra-confidential-7731"


async def test_permission_matrix(app: FastAPI, client: httpx.AsyncClient, search: SearchHarness) -> None:
    routes = [
        ("POST", "/api/v1/search"),
        ("GET", "/api/v1/search/suggest"),
        ("POST", "/api/v1/search/assist"),
        ("GET", "/api/v1/me/search-history"),
        ("DELETE", "/api/v1/me/search-history"),
        ("DELETE", "/api/v1/me/search-history/00000000-0000-7000-8000-000000000001"),
        ("GET", "/api/v1/palette/resolve"),
        ("POST", "/api/v1/admin/search/reindex"),
        ("GET", "/api/v1/admin/search/status"),
    ]
    for method, path in routes:
        assert (await client.request(method, path, json={"q": "x"})).status_code == 401, path
    await create_user(module_of(app), "plain")
    await login(client, "plain")
    for method, path in routes[-2:]:
        assert (await client.request(method, path, json={})).status_code == 403, path
    boss = await create_user(module_of(app), "boss")
    await make_admin(search.full, boss)
    await login(client, "boss")
    assert (await client.post("/api/v1/admin/search/reindex", json={"kinds": ["services"]})).json() == {
        "queued": ["services"]
    }
    status = (await client.get("/api/v1/admin/search/status")).json()
    assert {p["kind"] for p in status["providers"]} >= {"navigation", "services", "users"}
    assert status["semantic"]["available"] is False


async def test_ungranted_domain_contributes_nothing(
    app: FastAPI, client: httpx.AsyncClient, search: SearchHarness
) -> None:
    secret = FakeProvider("tickets", permission="audit.read", titles=("zebra ticket",))
    search.registry.register(secret, owner="module:support")
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    for body in ({"q": "zebra"}, {"q": "zebra", "kinds": ["tickets"]}, {"q": "type:tickets zebra"}):
        result = (await client.post("/api/v1/search", json=body)).json()
        assert "tickets" not in {g["kind"] for g in result["groups"]}
        assert result["total"] == 0
    assert secret.calls == 0
    suggest = (await client.get("/api/v1/search/suggest", params={"q": "zebra"})).json()
    assert suggest["items"] == []


async def test_changes_apply_on_next_search(
    app: FastAPI, client: httpx.AsyncClient, search: SearchHarness
) -> None:
    target = await create_user(module_of(app), "zed", display_name="Zed Visible")
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    first = (await client.post("/api/v1/search", json={"q": "zed", "kinds": ["users"]})).json()
    assert [i["title"] for i in first["groups"][0]["items"]] == ["Zed Visible"]
    await set_state(module_of(app), target, AccountState.SUSPENDED)
    again = (await client.post("/api/v1/search", json={"q": "zed", "kinds": ["users"]})).json()
    assert again["groups"][0]["items"] == []


async def test_markup_is_plain_text(app: FastAPI, client: httpx.AsyncClient, search: SearchHarness) -> None:
    payload = "<img src=x onerror=alert(1)>"
    search.registry.register(FakeProvider("notes", titles=(f"{payload} img",)), owner="module:notes")
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    body = (await client.post("/api/v1/search", json={"q": "img", "kinds": ["notes"]})).json()
    [item] = body["groups"][0]["items"]
    assert item["title"] == f"{payload} img"  # JSON text, never interpreted server side
    assert all(set(segment) == {"text", "hit"} for segment in item["snippet"])


async def test_no_query_text_in_events_or_logs(
    app: FastAPI, client: httpx.AsyncClient, search: SearchHarness, caplog: pytest.LogCaptureFixture
) -> None:
    await create_user(module_of(app), "alex")
    await login(client, "alex")

    async def down() -> list[object]:
        raise RuntimeError(SECRET_QUERY)  # even an error message carrying text is not logged

    search.directory.services = down  # type: ignore[method-assign]
    with caplog.at_level(logging.DEBUG):
        assert (await client.post("/api/v1/search", json={"q": SECRET_QUERY})).status_code == 200
        await search.module.drain()
    assert SECRET_QUERY not in caplog.text
    async with search.full.database.session() as session:
        rows = (await session.execute(text("SELECT type, metadata::text FROM core.event_outbox"))).all()
    types = {row[0] for row in rows}
    assert {"search.performed", "search.provider_failed"} <= types
    assert all(SECRET_QUERY not in row[1] for row in rows)
