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


async def test_a_play_profile_s_own_dashboard(
    app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness
) -> None:
    """#347: a free widget the administrator shows to some play profiles only — a member of another profile
    starts without it; one who did not answer plays it all."""
    for key in ("t.all", "t.cards", "t.games"):
        dash.registry.register(definition(key), FakeWidget())
    dash.module.config = replace(dash.module.config, widget_policies={}, starter_layout=[])
    boss = await create_user(module_of(app), "boss")
    await make_admin(dash.full, boss)
    await login(client, "boss")
    composition = {
        "items": [
            {"widget_key": "t.all", "x": 0, "y": 0, "w": 4, "h": 2},
            {"widget_key": "t.cards", "x": 4, "y": 0, "w": 4, "h": 2, "profiles": ["collector", "full"]},
            {"widget_key": "t.games", "x": 8, "y": 0, "w": 4, "h": 2, "profiles": ["full"]},
        ],
        "disabled": [],
    }
    saved = await client.put("/api/v1/admin/dashboard/composition", json=composition)
    assert saved.status_code == 200, saved.text
    back = {i["widget_key"]: i for i in saved.json()["items"]}
    assert back["t.cards"]["profiles"] == ["collector", "full"] and "profiles" not in back["t.all"]
    wrong = {"items": [{**composition["items"][0], "profiles": ["nope"]}], "disabled": []}
    assert (await client.put("/api/v1/admin/dashboard/composition", json=wrong)).status_code == 422

    async def started(login_name: str, play: str | None) -> set[str]:
        await create_user(module_of(app), login_name)
        await login(client, login_name)
        if play is not None:
            put = await client.put("/api/v1/me/preferences", json={"shell.onboarding.play": play})
            assert put.status_code == 200, put.text
        return {i["widget_key"] for i in (await client.get("/api/v1/dashboard")).json()["instances"]}

    assert await started("cleo", "collector") == {"t.all", "t.cards"}
    assert await started("pat", "progression") == {"t.all"}
    assert await started("sam", None) == {"t.all", "t.cards", "t.games"}


async def test_a_dashboard_made_to_the_member_s_tastes(
    app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness
) -> None:
    """#347: the welcome's « your portal to your taste » — the starter's widgets of the tastes not chosen left
    out, the chosen tastes' widgets it lacks added, a widget of no taste kept; no tastes: the default one;
    « just the media » leaves the game and the community out whatever the tastes."""
    for key in ("media.continue", "gamification.progress", "t.clock", "news.my_feed", "news.featured"):
        dash.registry.register(definition(key), FakeWidget())
    dash.module.config = replace(
        dash.module.config,
        widget_policies={},
        starter_layout=[
            {"widget_key": "media.continue", "x": 0, "y": 0, "w": 4, "h": 2},
            {"widget_key": "gamification.progress", "x": 4, "y": 0, "w": 4, "h": 2},
            {"widget_key": "t.clock", "x": 8, "y": 0, "w": 4, "h": 2},
        ],
    )
    await create_user(module_of(app), "alex")
    await login(client, "alex")

    async def keys() -> set[str]:
        return {i["widget_key"] for i in (await client.get("/api/v1/dashboard")).json()["instances"]}

    assert await keys() == {"media.continue", "gamification.progress", "t.clock"}
    made = await client.post("/api/v1/dashboard/reset", json={"tastes": ["watch", "news"]})
    assert made.status_code == 200, made.text
    assert await keys() == {"media.continue", "t.clock", "news.my_feed", "news.featured"}
    assert (await client.post("/api/v1/dashboard/reset", json={"tastes": ["nope"]})).status_code == 422
    assert (await client.post("/api/v1/dashboard/reset")).status_code == 200
    assert await keys() == {"media.continue", "gamification.progress", "t.clock"}
    # « just the media »: no game nor community on the home, even asked for
    play = await client.put("/api/v1/me/preferences", json={"shell.onboarding.play": "none"})
    assert play.status_code == 200, play.text
    asked = await client.post("/api/v1/dashboard/reset", json={"tastes": ["watch", "play", "community"]})
    assert asked.status_code == 200, asked.text
    assert await keys() == {"media.continue", "t.clock"}
    assert (await client.post("/api/v1/dashboard/reset")).status_code == 200
    assert await keys() == {"media.continue", "t.clock"}
