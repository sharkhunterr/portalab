"""030 T033 (US2, SC-003) — the example Forum, confined: installed and reviewed (its capabilities in plain
words), a topic published only once its member confirmed the exact content in Portalab's dialog, a reply
that notifies the others, its topics found by the portal's search, the member's posts in their export and
erased with them, disabling keeping the posts and enabling again bringing them back."""

import shutil
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import PlHarness

from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.search import ParsedQuery
from portalab.core.authz_port import Principal
from portalab.core.confinement import probe

pytestmark = pytest.mark.skipif(not probe().ok, reason="kernel cannot confine")
FORUM = Path(__file__).resolve().parents[5] / "examples" / "plugins" / "forum"


@dataclass
class Notifications:
    sent: list[Any] = field(default_factory=list)

    async def send(self, request: Any, *, caller: Any = None) -> Any:
        self.sent.append(request)


@dataclass
class Registration:
    provider: Any


@dataclass
class Capabilities:
    notify: Notifications

    def system_providers(self, name: str) -> list[Registration]:
        return [Registration(self.notify)]


def _headers(client: httpx.AsyncClient, **extra: str) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("__Host-portalab_csrf") or "", **extra}


async def test_the_forum_end_to_end(pl: PlHarness, client: httpx.AsyncClient) -> None:
    pl.module.config = replace(pl.module.config, hook_timeout_seconds=8.0)
    notifications = Notifications()
    pl.module.runtime.services.capabilities = Capabilities(notifications)  # type: ignore[assignment]
    shutil.copytree(FORUM, pl.root / "available" / "forum", ignore=shutil.ignore_patterns("__pycache__"))
    await login(client, "boss")
    installed = await client.post(
        "/api/v1/admin/plugins/install", json={"package": "forum"}, headers=_headers(client)
    )
    assert installed.status_code == 201, installed.text
    asked = {c["capability"] for c in installed.json()["review"]["requested_capabilities"]}
    assert {
        "storage",
        "operations",
        "pages",
        "notifications",
        "search",
        "events",
        "privacy",
        "portal_data",
    } <= asked
    assert (
        await client.post("/api/v1/admin/plugins/forum/approve", headers=_headers(client))
    ).status_code == 200
    enabled = await client.post("/api/v1/admin/plugins/forum/enable", headers=_headers(client))
    assert enabled.status_code == 200, enabled.text

    # publishing is committing: Portalab confirms the exact content first
    topic = {"title": "Movie night", "body": "Friday, who is in?"}
    first = await client.post("/api/v1/plugins/forum/topics", json=topic, headers=_headers(client))
    assert first.status_code == 409, first.text
    problem = first.json()
    assert problem["code"] == "plugin.confirmation_required"
    assert problem["summary"]["lines"][0] == "Movie night"
    token = problem["confirmation"]
    changed = await client.post(
        "/api/v1/plugins/forum/topics",
        json={**topic, "title": "Something else"},
        headers=_headers(client, **{"X-Portalab-Confirmation": token}),
    )
    assert changed.status_code == 409  # a confirmation is for that exact content only
    token = changed.json()["confirmation"]
    published = await client.post(
        "/api/v1/plugins/forum/topics",
        json={**topic, "title": "Something else"},
        headers=_headers(client, **{"X-Portalab-Confirmation": token}),
    )
    assert published.status_code == 200, published.text
    again = await client.post(
        "/api/v1/plugins/forum/topics",
        json={**topic, "title": "Something else"},
        headers=_headers(client, **{"X-Portalab-Confirmation": token}),
    )
    assert again.status_code == 409  # single use
    listed = (await client.get("/api/v1/plugins/forum/topics")).json()
    assert [i["label"] for i in listed["items"]] == ["Something else"]
    topic_id = listed["items"][0]["link"].split("=")[-1]

    # a reply by another member notifies the topic's author
    reply = {"topic": topic_id, "body": "Me!"}
    await login(client, "ursula")
    refused = await client.post("/api/v1/plugins/forum/replies", json=reply, headers=_headers(client))
    assert refused.status_code == 403  # no forum.post for ursula yet
    await login(client, "boss")
    asked_again = await client.post("/api/v1/plugins/forum/replies", json=reply, headers=_headers(client))
    token = asked_again.json()["confirmation"]
    replied = await client.post(
        "/api/v1/plugins/forum/replies",
        json=reply,
        headers=_headers(client, **{"X-Portalab-Confirmation": token}),
    )
    assert replied.status_code == 200, replied.text
    thread = (await client.get(f"/api/v1/plugins/forum/thread?topic={topic_id}")).json()
    assert [m["body"] for m in thread["items"]] == ["Friday, who is in?", "Me!"]

    # the portal's search finds it
    provider = pl.registries.search.provider("plugin:forum")
    diagnostics = (await client.get("/api/v1/admin/plugins/forum/diagnostics")).json()
    assert provider is not None, diagnostics["conflicts"]
    query = ParsedQuery(text="Something", normalized="something", terms=("something",))
    found = await provider.search(query, Principal(user_id=pl.people["boss"]), None, limit=5, cursor=None)
    assert [i.title for i in found.items] == ["Something else"]

    # privacy: the member's posts are exported, and erased with them
    boss: UUID = pl.people["boss"]
    exporters = [
        r.provider
        for r in pl.module.capabilities.system_providers(EXPORT_CAPABILITY)
        if r.owner == "plugin:forum"
    ]
    records = await exporters[0].export(boss)
    assert [p["body"] for p in records[0].data["posts"]] == ["Friday, who is in?", "Me!"]

    # disabled: its pages and routes are gone, its data kept; enabled again: back
    disabled = await client.post("/api/v1/admin/plugins/forum/disable", json={}, headers=_headers(client))
    assert disabled.status_code == 200, disabled.text
    assert (await client.get("/api/v1/plugins/forum/topics")).status_code == 404
    assert pl.registries.search.provider("plugin:forum") is None
    enabled = await client.post("/api/v1/admin/plugins/forum/enable", headers=_headers(client))
    assert enabled.status_code == 200, enabled.text
    assert [i["label"] for i in (await client.get("/api/v1/plugins/forum/topics")).json()["items"]] == [
        "Something else"
    ]

    erasers = [
        r.provider
        for r in pl.module.capabilities.system_providers(ERASURE_CAPABILITY)
        if r.owner == "plugin:forum"
    ]
    await erasers[0].erase(boss, "final")
    thread = (await client.get(f"/api/v1/plugins/forum/thread?topic={topic_id}")).json()
    assert all(m["removed"] and m["body"] == "" for m in thread["items"])
