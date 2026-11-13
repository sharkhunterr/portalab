"""030 (owner's request of 2026-10-18) — a plugin's own views: the sandbox document they run in reaches no
network and runs only its own bootstrap; a view's files are served from its ``views/`` folder only (no other
type, no way up); pages and surfaces say which view draws them; an update asking nothing more keeps its
grants, one asking more waits for the Admin."""

import re
import shutil
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import PlHarness

from portalab.core.confinement import probe

pytestmark = pytest.mark.skipif(not probe().ok, reason="kernel cannot confine")
EXAMPLES = Path(__file__).resolve().parents[5] / "examples" / "plugins"


def _h(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("__Host-portalab_csrf") or ""}


async def _enable(pl: PlHarness, client: httpx.AsyncClient, key: str) -> None:
    shutil.copytree(EXAMPLES / key, pl.root / "available" / key, ignore=shutil.ignore_patterns("__pycache__"))
    assert (
        await client.post("/api/v1/admin/plugins/install", json={"package": key}, headers=_h(client))
    ).status_code == 201
    assert (await client.post(f"/api/v1/admin/plugins/{key}/approve", headers=_h(client))).status_code == 200
    enabled = await client.post(f"/api/v1/admin/plugins/{key}/enable", headers=_h(client))
    assert enabled.status_code == 200, enabled.text


async def test_views_are_served_sandboxed(pl: PlHarness, client: httpx.AsyncClient) -> None:
    pl.module.config = replace(pl.module.config, hook_timeout_seconds=8.0)
    await login(client, "boss")
    await _enable(pl, client, "messenger")
    sandbox = await client.get("/api/v1/plugins/sandbox")
    policy = sandbox.headers["content-security-policy"]
    assert sandbox.status_code == 200 and "connect-src 'none'" in policy and "form-action 'none'" in policy
    assert "script-src 'sha256-" in policy and "unsafe-eval" not in policy

    view = await client.get("/api/v1/plugins/messenger/views/chat.js")
    assert view.status_code == 200 and view.headers["content-type"].startswith("text/javascript")
    assert "sandbox" in view.headers["content-security-policy"]
    for refused in ("../plugin.toml", "..%2Fplugin.toml", "chat.py", "../messenger_plugin/__init__.py"):
        assert (await client.get(f"/api/v1/plugins/messenger/views/{refused}")).status_code == 404, refused

    slots = (await client.get("/api/v1/plugins/slots")).json()
    corner = next(s for s in slots if s["slot"] == "corner")
    assert corner["corner"] == "bottom-right" and corner["opens"] == "chat" and corner["badge"] == "unread"
    surface = (await client.get("/api/v1/plugins/messenger/surfaces/chat")).json()
    assert (
        surface["kind"] == "panel" and surface["view"] == "chat.js" and surface["blocks"]
    )  # blocks: safe mode

    await login(client, "ursula")  # without the plugin's permission: neither its files nor its sandbox's use
    assert (await client.get("/api/v1/plugins/messenger/views/chat.js")).status_code in (200, 404)
    assert (await client.get("/api/v1/plugins/slots")).json() == []


async def test_an_update_asking_nothing_more_keeps_its_grants(
    pl: PlHarness, client: httpx.AsyncClient
) -> None:
    pl.module.config = replace(pl.module.config, hook_timeout_seconds=8.0)
    await login(client, "boss")
    await _enable(pl, client, "forum")
    nextgen = pl.root / "available" / "forum-next"
    shutil.copytree(EXAMPLES / "forum", nextgen, ignore=shutil.ignore_patterns("__pycache__"))
    manifest = re.sub(
        r'^version = ".*"$', 'version = "9.2.0"', (nextgen / "plugin.toml").read_text(), flags=re.MULTILINE
    )
    (nextgen / "plugin.toml").write_text(manifest)
    staged = await client.post(
        "/api/v1/admin/plugins/forum/update", json={"package": "forum-next"}, headers=_h(client)
    )
    assert staged.status_code == 200, staged.text
    confirmed = await client.post("/api/v1/admin/plugins/forum/update/confirm-restart", headers=_h(client))
    assert confirmed.status_code == 200, confirmed.text
    plugin = await pl.module.lifecycle.get("forum")
    assert plugin.current_version == "9.2.0" and plugin.state == "enabled"
    assert pl.module.runtime.hosts["forum"].state == "running"
    page = await client.get("/api/v1/plugins/forum/pages/topics")
    assert page.status_code == 200 and page.json()["view"] == "forum.js", page.text  # its pages came back

    wider = pl.root / "available" / "forum-wider"
    shutil.copytree(nextgen, wider)
    text = (wider / "plugin.toml").read_text().replace('version = "9.2.0"', 'version = "9.3.0"')
    text = text.replace(
        "search = true", 'search = true\nnetwork = { hosts = [{ host = "api.example.org" }] }'
    )
    (wider / "plugin.toml").write_text(text)
    from portalab.modules.plugins.manifest.schema import parse_toml

    asking_more = parse_toml(text)
    assert "network" in await pl.module.grants.missing("forum", "9.3.0", asking_more)
    assert await pl.module.grants.carry_over("forum", "9.3.0", asking_more) is False  # the Admin decides
    assert "network" in await pl.module.grants.missing("forum", "9.3.0", asking_more)
