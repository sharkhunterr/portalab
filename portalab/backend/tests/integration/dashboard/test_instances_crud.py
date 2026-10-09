"""009 T016/T023/T024 — add/hide/remove/reorder/resize/configure persisted; hide keeps the config and re-add
restores it; remove discards it; ``If-Match`` conflict ⇒ 409; invalid config ⇒ 422; unavailable/unpermitted
widget cannot be added; single-instance rule; policies enforced server-side (mandatory, locked, disabled)
and relaxing a policy restores the user's state; admin policy API is guarded, validated and audited."""

import httpx
import pytest
from fastapi import FastAPI

from tests.authz_fixtures import make_admin
from tests.integration.dashboard.conftest import DashboardHarness
from tests.integration.identity.helpers import create_user, login, module_of
from tests.unit.dashboard.fakes import FakeWidget, definition

pytestmark = pytest.mark.integration


def register(dash: DashboardHarness) -> None:
    dash.registry.register(definition("t.one"), FakeWidget())
    dash.registry.register(definition("t.two"), FakeWidget())
    dash.registry.register(definition("t.many", multiple=True), FakeWidget())
    dash.registry.register(definition("t.secret", required_permission="audit.read"), FakeWidget())


async def board(client: httpx.AsyncClient) -> dict[str, object]:
    return (await client.get("/api/v1/dashboard")).json()


def by_key(view: dict[str, object]) -> dict[str, dict[str, object]]:
    return {i["widget_key"]: i for i in view["instances"]}  # type: ignore[index, union-attr]


async def test_personalization(app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness) -> None:
    register(dash)
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    first = await board(client)
    starter = [i["widget_key"] for i in first["instances"]]  # type: ignore[index, union-attr]
    # starter applied on first view: the widgets this member can use, in the starter's order (027)
    assert starter == [
        "dashboard.welcome",
        "dashboard.since_last_visit",
        "health.services_summary",
        "health.service_links",
    ]
    version = first["layout_version"]
    added = await client.post(
        "/api/v1/dashboard/widgets",
        json={"widget_key": "t.one", "config": {"limit": 3}, "w": 6, "h": 3},
        headers={"If-Match": str(version)},
    )
    assert added.status_code == 201
    one = added.json()["id"]
    stale = await client.post(
        "/api/v1/dashboard/widgets", json={"widget_key": "t.two"}, headers={"If-Match": str(version)}
    )
    assert stale.status_code == 409 and stale.json()["code"] == "dashboard.version_conflict"
    assert (await client.post("/api/v1/dashboard/widgets", json={"widget_key": "t.one"})).json()[
        "code"
    ] == "dashboard.widget_exists"
    assert (await client.post("/api/v1/dashboard/widgets", json={"widget_key": "t.many"})).status_code == 201
    assert (await client.post("/api/v1/dashboard/widgets", json={"widget_key": "t.many"})).status_code == 201
    for key in ("t.secret", "t.unknown"):
        refused = await client.post("/api/v1/dashboard/widgets", json={"widget_key": key})
        assert refused.status_code == 422 and refused.json()["code"] == "dashboard.widget_unavailable"
    invalid = await client.patch(f"/api/v1/dashboard/widgets/{one}", json={"config": {"limit": 50}})
    assert invalid.status_code == 422 and invalid.json()["code"] == "dashboard.config_invalid"
    assert (
        await client.patch(f"/api/v1/dashboard/widgets/{one}", json={"w": 12, "h": 1, "position": 0})
    ).status_code == 200
    view = by_key(await board(client))
    assert (view["t.one"]["w"], view["t.one"]["h"], view["t.one"]["position"]) == (
        8,
        1,
        0,
    )  # clamped to limits
    await client.patch(f"/api/v1/dashboard/widgets/{one}", json={"status": "hidden"})
    assert by_key(await board(client))["t.one"]["status"] == "hidden"
    readd = await client.post("/api/v1/dashboard/widgets", json={"widget_key": "t.one"})
    assert readd.json()["id"] == one and by_key(await board(client))["t.one"]["config"] == {"limit": 3}
    assert (await client.delete(f"/api/v1/dashboard/widgets/{one}")).status_code == 200
    fresh = (await client.post("/api/v1/dashboard/widgets", json={"widget_key": "t.one"})).json()["id"]
    assert fresh != one and by_key(await board(client))["t.one"]["config"] == {"limit": 5}  # config discarded
    catalog = {c["key"]: c["placed"] for c in (await client.get("/api/v1/dashboard/catalog")).json()}
    assert "t.secret" not in catalog and catalog["t.one"] is True
    await create_user(module_of(app), "sam")
    await login(client, "sam")
    assert (await client.delete(f"/api/v1/dashboard/widgets/{fresh}")).status_code == 404  # not sam's


async def test_layout_batch(app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness) -> None:
    register(dash)
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    await board(client)
    await client.post("/api/v1/dashboard/widgets", json={"widget_key": "t.one"})
    items = (await board(client))["instances"]
    order = [{"id": i["id"], "widget_key": i["widget_key"], "w": 4, "h": 2} for i in reversed(items)]  # type: ignore[union-attr]
    assert (await client.put("/api/v1/dashboard/layout", json={"items": order})).status_code == 200
    assert [i["widget_key"] for i in (await board(client))["instances"]] == [o["widget_key"] for o in order]  # type: ignore[union-attr]


async def test_policies(app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness) -> None:
    register(dash)
    boss = await create_user(module_of(app), "boss")
    await make_admin(dash.full, boss)
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    await board(client)
    one = (
        await client.post("/api/v1/dashboard/widgets", json={"widget_key": "t.one", "config": {"limit": 2}})
    ).json()["id"]
    await client.patch(f"/api/v1/dashboard/widgets/{one}", json={"status": "hidden"})
    assert (await client.get("/api/v1/admin/dashboard/policies")).status_code == 403

    await login(client, "boss")
    bad = await client.put("/api/v1/admin/dashboard/policies", json={"t.nope": {"class": "mandatory"}})
    assert bad.status_code == 422
    policies = {
        "t.one": {"class": "mandatory"},
        "t.two": {"class": "mandatory"},
        "dashboard.welcome": {"class": "disabled"},
        "health.services_summary": {"class": "locked", "lockedConfig": {"show": "problems"}},
    }
    assert (await client.put("/api/v1/admin/dashboard/policies", json=policies)).status_code == 200

    await login(client, "alex")
    view = by_key(await board(client))
    assert "dashboard.welcome" not in view
    assert (
        view["t.one"]["status"] == "active" and view["t.one"]["mandatory"] and not view["t.one"]["removable"]
    )
    assert view["t.two"]["id"] is None  # synthesized for everyone, not stored
    locked = view["health.services_summary"]
    assert locked["locked"] and locked["config"]["show"] == "problems"
    for request in (
        client.patch(f"/api/v1/dashboard/widgets/{one}", json={"status": "hidden"}),
        client.delete(f"/api/v1/dashboard/widgets/{one}"),
        client.patch(f"/api/v1/dashboard/widgets/{locked['id']}", json={"w": 3}),
    ):
        refused = await request
        assert refused.status_code == 409 and refused.json()["code"] == "dashboard.policy_locked"
    assert (
        await client.post("/api/v1/dashboard/widgets", json={"widget_key": "dashboard.welcome"})
    ).status_code == 422

    await login(client, "boss")
    await client.put("/api/v1/admin/dashboard/policies", json={})
    await login(client, "alex")
    restored = by_key(await board(client))
    assert restored["t.one"]["status"] == "hidden" and restored["t.one"]["config"] == {
        "limit": 2
    }  # prior state back
    assert "t.two" not in restored and "dashboard.welcome" in restored
    assert restored["health.services_summary"]["config"]["show"] == "all"


async def test_pinned_and_reset(app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness) -> None:
    """027: a pinned widget is on every dashboard at the administrator's place — not removable, hideable
    or movable; « default » brings the starter dashboard back."""
    register(dash)
    boss = await create_user(module_of(app), "boss")
    await make_admin(dash.full, boss)
    await login(client, "boss")
    pins = {
        "t.one": {"class": "pinned", "x": 0, "y": 0, "w": 6, "h": 2},
        "t.two": {"class": "pinned", "x": 6, "y": 0, "w": 6, "h": 2},
    }
    assert (await client.put("/api/v1/admin/dashboard/policies", json=pins)).status_code == 200

    await create_user(module_of(app), "alex")
    await login(client, "alex")
    view = by_key(await board(client))
    assert (view["t.one"]["x"], view["t.one"]["y"], view["t.two"]["x"], view["t.two"]["y"]) == (0, 0, 6, 0)
    assert view["t.one"]["mandatory"] and view["t.one"]["locked"]
    assert all(i["y"] >= 2 for k, i in view.items() if k not in pins)  # the others start below
    one = view["t.one"]["id"]
    assert (await client.delete(f"/api/v1/dashboard/widgets/{one}")).status_code == 409
    assert (await client.patch(f"/api/v1/dashboard/widgets/{one}", json={"x": 4})).status_code == 409
    moved = await client.put(
        "/api/v1/dashboard/arrangement",
        json={"items": [{"id": one, "widget_key": "t.one", "x": 2, "y": 5, "w": 4, "h": 3}]},
    )
    assert moved.status_code == 200
    view = by_key(await board(client))
    assert (view["t.one"]["x"], view["t.one"]["y"], view["t.one"]["w"]) == (0, 0, 6)  # stays put

    assert not view["t.one"]["movable"] and not view["t.one"]["resizable"]

    # 027: the administrator may let members move (and/or resize) a pinned widget — it still cannot go
    await login(client, "boss")
    pins["t.one"] = {**pins["t.one"], "move": True}
    assert (await client.put("/api/v1/admin/dashboard/policies", json=pins)).status_code == 200
    await login(client, "alex")
    view = by_key(await board(client))
    assert view["t.one"]["movable"] and not view["t.one"]["resizable"]
    assert (await client.patch(f"/api/v1/dashboard/widgets/{one}", json={"x": 4, "y": 6})).status_code == 200
    assert (await client.patch(f"/api/v1/dashboard/widgets/{one}", json={"w": 3})).status_code == 409
    view = by_key(await board(client))
    assert (view["t.one"]["x"], view["t.one"]["w"]) == (4, 6) and view["t.one"]["mandatory"]
    assert (await client.delete(f"/api/v1/dashboard/widgets/{one}")).status_code == 409

    welcome = view["dashboard.welcome"]["id"]
    assert (await client.delete(f"/api/v1/dashboard/widgets/{welcome}")).status_code == 200
    assert (await client.post("/api/v1/dashboard/widgets", json={"widget_key": "t.many"})).status_code == 201
    reset = await client.post("/api/v1/dashboard/reset")
    assert reset.status_code == 200, reset.text
    view = by_key(await board(client))
    assert "dashboard.welcome" in view and "t.many" not in view and view["t.two"]["x"] == 6
