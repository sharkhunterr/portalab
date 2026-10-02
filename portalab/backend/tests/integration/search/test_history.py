"""008 T025 — history is personal data: recorded on search (upsert per normalized query), capped and
retention-limited, clearable one/all, disabled by ``search.historyEnabled``, private to its owner, and
included in the export / erased with the account (privacy participants)."""

from dataclasses import replace
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.core.authz_port import Principal
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.search.conftest import SearchHarness

pytestmark = pytest.mark.integration


async def run(client: httpx.AsyncClient, search: SearchHarness, q: str) -> None:
    assert (await client.post("/api/v1/search", json={"q": q})).status_code == 200
    await search.module.drain()


async def test_history_lifecycle(app: FastAPI, client: httpx.AsyncClient, search: SearchHarness) -> None:
    alex = await create_user(module_of(app), "alex")
    await login(client, "alex")
    search.module.config = replace(search.module.config, history_max_entries=2)
    await run(client, search, "Jellyfin")
    await run(client, search, "jellyfin ")  # same normalized query: upsert
    history = (await client.get("/api/v1/me/search-history")).json()
    assert len(history) == 1 and history[0]["count"] == 2 and history[0]["query"] == "jellyfin"
    await run(client, search, "books")
    await run(client, search, "media type:services")
    history = (await client.get("/api/v1/me/search-history")).json()
    assert [h["query"] for h in history] == ["media type:services", "books"]  # capped at 2
    assert history[0]["filters"] == {"type": ["services"]}
    assert (await client.delete(f"/api/v1/me/search-history/{history[1]['id']}")).status_code == 204
    assert (await client.delete(f"/api/v1/me/search-history/{history[1]['id']}")).status_code == 404
    contributors = [
        p.provider
        for p in search.full.identity.capabilities.system_providers(EXPORT_CAPABILITY)
        if p.instance_ref == "search.history"
    ]
    [record] = await contributors[0].export(alex)
    assert record.category == "search.history" and record.data["query"] == "media type:services"
    assert (await client.delete("/api/v1/me/search-history")).status_code == 204
    assert (await client.get("/api/v1/me/search-history")).json() == []


async def test_history_is_private_and_erased(
    app: FastAPI, client: httpx.AsyncClient, search: SearchHarness
) -> None:
    alex = await create_user(module_of(app), "alex")
    await create_user(module_of(app), "sam")
    await login(client, "alex")
    await run(client, search, "secret plans")
    [entry] = (await client.get("/api/v1/me/search-history")).json()
    await login(client, "sam")
    assert (await client.get("/api/v1/me/search-history")).json() == []
    assert (await client.delete(f"/api/v1/me/search-history/{entry['id']}")).status_code == 404  # not sam's
    assert await search.module.history.count(alex) == 1
    erasers = [
        p.provider
        for p in search.full.identity.capabilities.system_providers(ERASURE_CAPABILITY)
        if p.instance_ref == "search.history"
    ]
    await erasers[0].erase(alex, "final")
    await erasers[0].erase(alex, "final")  # idempotent
    assert await search.module.history.count(alex) == 0


async def test_opt_out_and_retention(app: FastAPI, client: httpx.AsyncClient, search: SearchHarness) -> None:
    alex = await create_user(module_of(app), "alex")
    await login(client, "alex")
    await search.full.administration.config.set(
        "search.historyEnabled", False, scope="user", scope_ref=str(alex), actor=Principal(user_id=alex)
    )
    await run(client, search, "not kept")
    assert await search.module.history.count(alex) == 0
    await search.full.administration.config.set(
        "search.historyEnabled", True, scope="user", scope_ref=str(alex), actor=Principal(user_id=alex)
    )
    await run(client, search, "kept for a while")
    assert await search.module.history.count(alex) == 1
    search.module.history.clock.advance(timedelta(days=91))  # type: ignore[union-attr]
    assert await search.module.history.purge_expired() == 1
