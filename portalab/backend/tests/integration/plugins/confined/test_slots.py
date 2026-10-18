"""030 T040 (US1b) — slots: an enabled plugin's « + Playlist » action is offered on media pages to the members
holding its permission only, it opens a modal Portalab draws from the plugin's blocks; its page and edit modal
work; deleting a playlist is confirmed by Portalab; disabled, nothing of it is offered any more."""

import asyncio
import shutil
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import PlHarness

from portalab.core.confinement import probe

pytestmark = pytest.mark.skipif(not probe().ok, reason="kernel cannot confine")
PLAYLIST = Path(__file__).resolve().parents[5] / "examples" / "plugins" / "playlist"


def _h(client: httpx.AsyncClient, **extra: str) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("__Host-portalab_csrf") or "", **extra}


async def test_a_plugin_adds_an_action_to_media_pages(pl: PlHarness, client: httpx.AsyncClient) -> None:
    pl.module.config = replace(pl.module.config, hook_timeout_seconds=8.0)
    shutil.copytree(
        PLAYLIST, pl.root / "available" / "playlist", ignore=shutil.ignore_patterns("__pycache__")
    )
    await login(client, "boss")
    assert (
        await client.post("/api/v1/admin/plugins/install", json={"package": "playlist"}, headers=_h(client))
    ).status_code == 201
    assert (
        await client.post("/api/v1/admin/plugins/playlist/approve", headers=_h(client))
    ).status_code == 200
    enabled = await client.post("/api/v1/admin/plugins/playlist/enable", headers=_h(client))
    assert enabled.status_code == 200, enabled.text

    slots = (await client.get("/api/v1/plugins/slots")).json()
    assert [(s["slot"], s["id"], s["opens"]) for s in slots] == [("media.actions", "playlist:add", "add_to")]
    modal = (await client.get("/api/v1/plugins/playlist/surfaces/add_to")).json()
    assert modal["kind"] == "modal" and [b["kind"] for b in modal["blocks"]] == ["checklist", "form"]
    assert modal["blocks"][0]["action"] == "toggle"

    await login(client, "ursula")  # no plugin:playlist.use: nothing offered, nothing reachable
    assert (await client.get("/api/v1/plugins/slots")).json() == []
    assert (await client.get("/api/v1/plugins/playlist/surfaces/add_to")).status_code == 404

    await login(client, "boss")
    created = await client.post(
        "/api/v1/plugins/playlist/playlists", json={"name": "Friday"}, headers=_h(client)
    )
    assert created.status_code == 200, created.text
    mine = (await client.get("/api/v1/plugins/playlist/mine")).json()
    link = mine["items"][0]["link"]
    playlist = link.split("=")[-1]
    assert mine["items"][0]["title"] == "Friday"
    # calls of one plugin run at the same time: each gets its own answer (the storage keeps nothing shared)
    together = await asyncio.gather(
        *[client.get(f"/api/v1/plugins/playlist/values?playlist={playlist}") for _ in range(6)],
        *[client.get("/api/v1/plugins/playlist/mine") for _ in range(6)],
    )
    bodies = [r.text[:160] for r in together]
    assert all(r.status_code == 200 for r in together), bodies
    assert all(r.json()["values"]["name"] == "Friday" for r in together[:6]), bodies
    assert all(r.json()["items"][0]["title"] == "Friday" for r in together[6:])
    values = (await client.get(f"/api/v1/plugins/playlist/values?playlist={playlist}")).json()
    assert values["values"]["name"] == "Friday"
    saved = await client.post(
        "/api/v1/plugins/playlist/update",
        json={"playlist": playlist, "name": "Saturday", "description": "x"},
        headers=_h(client),
    )
    assert saved.json()["message"] == "Saved."
    page = (await client.get("/api/v1/plugins/playlist/pages/list")).json()
    assert page["blocks"][0] == {
        "kind": "actions",
        "buttons": [
            {"label_key": "plugin.playlist:action.edit", "opens": "edit"},
            {
                "label_key": "plugin.playlist:action.delete",
                "action": "delete",
                "then": "/plugins/playlist/mine",
            },
        ],
    }
    first = await client.post(
        "/api/v1/plugins/playlist/delete", json={"playlist": playlist}, headers=_h(client)
    )
    assert first.status_code == 409 and first.json()["summary"]["lines"] == ["Saturday"]
    token = first.json()["confirmation"]
    deleted = await client.post(
        "/api/v1/plugins/playlist/delete",
        json={"playlist": playlist},
        headers=_h(client, **{"X-Portalab-Confirmation": token}),
    )
    assert deleted.status_code == 200 and deleted.json()["link"] == "/plugins/playlist/mine"

    assert (
        await client.post("/api/v1/admin/plugins/playlist/disable", json={}, headers=_h(client))
    ).status_code == 200
    assert (await client.get("/api/v1/plugins/slots")).json() == []
