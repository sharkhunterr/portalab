"""Issue 250 — the administrator composes the default dashboard: each widget at its very place, with its own
settings and its lock (free, always there, locked); what a new member gets is exactly that, and the
composition reads back as it was written. Only an administrator composes it; a wrong setting is refused and
nothing is written."""

from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI

from tests.authz_fixtures import make_admin
from tests.integration.dashboard.conftest import DashboardHarness
from tests.integration.identity.helpers import create_user, login, module_of
from tests.unit.dashboard.fakes import FakeWidget, definition

pytestmark = pytest.mark.integration


async def test_composition(app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness) -> None:
    for key in ("t.free", "t.always", "t.locked", "t.off"):
        dash.registry.register(definition(key), FakeWidget())
    dash.module.config = replace(dash.module.config, widget_policies={}, starter_layout=[])
    boss = await create_user(module_of(app), "boss")
    await make_admin(dash.full, boss)
    await login(client, "boss")
    composition = {
        "items": [
            {
                "widget_key": "t.locked",
                "x": 0,
                "y": 0,
                "w": 6,
                "h": 2,
                "lock": "locked",
                "config": {"limit": 2},
            },
            {"widget_key": "t.free", "x": 6, "y": 0, "w": 4, "h": 2, "config": {"limit": 7}},
            {
                "widget_key": "t.always",
                "x": 2,
                "y": 3,
                "w": 4,
                "h": 2,
                "lock": "always",
                "phone": {"x": 0, "y": 0, "w": 4, "h": 2},
            },
        ],
        "disabled": ["t.off"],
    }
    saved = await client.put("/api/v1/admin/dashboard/composition", json=composition)
    assert saved.status_code == 200, saved.text
    back = {i["widget_key"]: i for i in saved.json()["items"]}
    assert {k: back["t.free"][k] for k in ("x", "y", "w", "h", "lock")} == {
        "x": 6,
        "y": 0,
        "w": 4,
        "h": 2,
        "lock": "free",
    }
    assert back["t.free"]["config"]["limit"] == 7
    assert back["t.locked"]["lock"] == "locked" and back["t.locked"]["config"]["limit"] == 2
    assert back["t.always"]["lock"] == "always" and back["t.always"]["phone"]["w"] == 4
    assert saved.json()["disabled"] == ["t.off"]
    # what it is written as: the pinned policy with its settings, a mandatory one, the starter's places
    policies = dash.module.config.widget_policies
    assert policies["t.locked"] == {
        "class": "pinned",
        "x": 0,
        "y": 0,
        "w": 6,
        "h": 2,
        "lockedConfig": {"limit": 2},
    }
    assert policies["t.always"] == {"class": "mandatory"} and policies["t.off"] == {"class": "disabled"}
    assert [e["widget_key"] for e in dash.module.config.starter_layout] == ["t.free", "t.always"]

    # a new member's dashboard is that one
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    instances = {i["widget_key"]: i for i in (await client.get("/api/v1/dashboard")).json()["instances"]}
    assert set(instances) == {"t.free", "t.always", "t.locked"}
    assert (instances["t.free"]["x"], instances["t.free"]["y"]) == (6, 0)
    assert (instances["t.always"]["x"], instances["t.always"]["y"]) == (2, 3)
    assert instances["t.free"]["config"]["limit"] == 7
    assert instances["t.locked"]["config"]["limit"] == 2 and instances["t.locked"]["locked"] is True
    assert instances["t.always"]["removable"] is False and instances["t.always"]["movable"] is True
    locked = await client.get(
        "/api/v1/widgets/t.locked/data", params={"instance": instances["t.locked"]["id"]}
    )
    assert locked.status_code == 200
    # the members' own settings window cannot change what is locked
    refused = await client.patch(
        f"/api/v1/dashboard/widgets/{instances['t.locked']['id']}", json={"config": {"limit": 9}}
    )
    assert refused.status_code == 409
    # only an administrator composes it
    assert (await client.get("/api/v1/admin/dashboard/composition")).status_code == 403


async def test_composition_refused_whole(
    app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness
) -> None:
    dash.registry.register(definition("t.one"), FakeWidget())
    before = (dash.module.config.widget_policies, dash.module.config.starter_layout)
    boss = await create_user(module_of(app), "boss")
    await make_admin(dash.full, boss)
    await login(client, "boss")
    wrong = {"items": [{"widget_key": "t.one", "x": 0, "y": 0, "w": 4, "h": 2, "config": {"limit": 99}}]}
    refused = await client.put("/api/v1/admin/dashboard/composition", json=wrong)
    assert refused.status_code == 422 and refused.json()["code"] == "dashboard.invalid_policy"
    twice = {"items": [{"widget_key": "t.one", "x": 0, "y": 0, "w": 4, "h": 2}] * 2}
    assert (await client.put("/api/v1/admin/dashboard/composition", json=twice)).status_code == 422
    assert (dash.module.config.widget_policies, dash.module.config.starter_layout) == before
