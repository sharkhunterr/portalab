"""030 T034 (US6, FR-020a) — 023's plugins after confinement: declarative ones unchanged; code running inside
Portalab is held on a new install (with how to move on), runs when it was installed before confinement or
when the Admin allows it, and the Admin always sees that it is not confined."""

from dataclasses import replace

import httpx
from sqlalchemy import update
from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import PlHarness

from portalab.modules.plugins.models import Plugin


def _headers(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("__Host-portalab_csrf") or ""}


async def _install(pl: PlHarness, client: httpx.AsyncClient) -> None:
    pl.hello()
    await login(client, "boss")
    assert (
        await client.post(
            "/api/v1/admin/plugins/install", json={"package": "hello"}, headers=_headers(client)
        )
    ).status_code == 201
    assert (
        await client.post("/api/v1/admin/plugins/hello/approve", headers=_headers(client))
    ).status_code == 200


async def test_code_inside_portalab_is_held_on_a_new_install(
    pl: PlHarness, client: httpx.AsyncClient
) -> None:
    pl.module.config = replace(pl.module.config, unconfined="existing")
    await _install(pl, client)
    held = await client.post("/api/v1/admin/plugins/hello/enable", headers=_headers(client))
    assert held.status_code == 409 and held.json()["code"] == "plugin.held_unconfined", held.text
    plugin = await pl.module.lifecycle.get("hello")
    assert plugin.state == "held_unconfined" and plugin.runtime == "in_process"
    assert not any(c.owner == "plugin:hello" for c in pl.registries.navigation.all())  # nothing of it shows
    detail = (await client.get("/api/v1/admin/plugins/hello/confinement")).json()
    assert detail["warning"] == "unconfined"

    pl.module.config = replace(pl.module.config, unconfined="allow")  # the Admin allows it
    enabled = await client.post("/api/v1/admin/plugins/hello/enable", headers=_headers(client))
    assert enabled.status_code == 200 and enabled.json()["state"] == "enabled", enabled.text


async def test_code_installed_before_confinement_keeps_running(
    pl: PlHarness, client: httpx.AsyncClient
) -> None:
    pl.module.config = replace(pl.module.config, unconfined="existing")
    await _install(pl, client)
    async with pl.database.unit_of_work() as uow:  # what the 030 migration marks on an upgraded install
        await uow.session.execute(
            update(Plugin).where(Plugin.key == "hello").values(predates_confinement=True)
        )
    enabled = await client.post("/api/v1/admin/plugins/hello/enable", headers=_headers(client))
    assert enabled.status_code == 200 and enabled.json()["state"] == "enabled", enabled.text

    pl.module.config = replace(pl.module.config, unconfined="refuse")
    loaded = await pl.module.lifecycle.load_enabled()  # a restart with in-process code refused
    assert "hello" not in loaded
    assert (await pl.module.lifecycle.get("hello")).state == "held_unconfined"
