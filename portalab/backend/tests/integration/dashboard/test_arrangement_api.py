"""027 T068 — the 2D arrangement API: ``GET /dashboard`` carries grid coordinates; ``PUT
/dashboard/arrangement`` stores a desktop arrangement (If-Match, bounds and size limits, overlap resolution
and compaction, reading-order ``position``, omitted widgets kept, locked widgets refused); ``POST`` places a
new widget at the first free slot or where it was dropped; ``PATCH`` moves and resizes with neighbours
making room; the deprecated ``PUT /dashboard/layout`` still works."""

from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from tests.authz_fixtures import make_admin
from tests.integration.dashboard.conftest import DashboardHarness
from tests.integration.dashboard.test_instances_crud import board, by_key, register
from tests.integration.identity.helpers import create_user, login, module_of

pytestmark = pytest.mark.integration


def cells(view: dict[str, Any]) -> dict[str, tuple[int, int, int, int]]:
    return {
        i["widget_key"]: (i["x"], i["y"], i["w"], i["h"])
        for i in view["instances"]
        if i["status"] == "active"
    }


def no_overlap(view: dict[str, Any]) -> bool:
    boxes = list(cells(view).values())
    return not any(
        a is not b and a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]
        for a in boxes
        for b in boxes
    )


async def test_arrangement(app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness) -> None:
    register(dash)
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    first = await board(client)
    assert all({"x", "y"} <= set(i) for i in first["instances"])
    one = (await client.post("/api/v1/dashboard/widgets", json={"widget_key": "t.one"})).json()["id"]
    view = await board(client)
    assert no_overlap(view)
    version = view["layout_version"]
    items = [
        {"id": i["id"], "widget_key": i["widget_key"], "x": i["x"], "y": i["y"], "w": i["w"], "h": i["h"]}
        for i in view["instances"]
    ]
    target = next(item for item in items if item["id"] == one)
    for item in items:  # the editor sends an arrangement already resolved by the shared engine
        item["y"] += 2
    target.update(x=0, y=0, w=8, h=2)
    stale = await client.put(
        "/api/v1/dashboard/arrangement", json={"items": items}, headers={"If-Match": str(version - 1)}
    )
    assert stale.status_code == 409 and stale.json()["code"] == "dashboard.version_conflict"
    saved = await client.put(
        "/api/v1/dashboard/arrangement", json={"items": items}, headers={"If-Match": str(version)}
    )
    assert saved.status_code == 200, saved.text
    view = await board(client)
    assert cells(view)["t.one"] == (0, 0, 8, 2) and no_overlap(view)
    ordered = sorted(view["instances"], key=lambda i: i["position"])
    assert ordered[0]["widget_key"] == "t.one"  # reading order follows the grid

    big = [{**target, "w": 12, "h": 9}]  # beyond the widget's limits (max 8 by 4): clamped, never refused
    assert (await client.put("/api/v1/dashboard/arrangement", json={"items": big})).status_code == 200
    view = await board(client)
    assert cells(view)["t.one"][2:] == (8, 4) and len(cells(view)) == 3  # omitted widgets are kept
    outside = [{**target, "x": 12}]
    assert (await client.put("/api/v1/dashboard/arrangement", json={"items": outside})).status_code == 422

    dropped = await client.post("/api/v1/dashboard/widgets", json={"widget_key": "t.two", "x": 0, "y": 0})
    assert dropped.status_code == 201
    view = await board(client)
    assert cells(view)["t.two"][:2] == (0, 0) and no_overlap(view)
    moved = await client.patch(f"/api/v1/dashboard/widgets/{one}", json={"x": 4, "y": 0})
    assert moved.status_code == 200 and no_overlap(await board(client))
    resized = await client.patch(f"/api/v1/dashboard/widgets/{one}", json={"w": 2, "h": 1})
    assert resized.status_code == 200 and cells(await board(client))["t.one"][2:] == (2, 1)

    legacy = [
        {"id": i["id"], "widget_key": i["widget_key"], "w": i["w"], "h": i["h"]} for i in view["instances"]
    ]
    assert (await client.put("/api/v1/dashboard/layout", json={"items": legacy[::-1]})).status_code == 200
    assert no_overlap(await board(client))


async def test_locked_widgets_cannot_be_rearranged(
    app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness
) -> None:
    register(dash)
    boss = await create_user(module_of(app), "boss")
    await make_admin(dash.full, boss)
    await create_user(module_of(app), "alex")
    await login(client, "boss")
    policies = {"health.services_summary": {"class": "locked"}}
    assert (await client.put("/api/v1/admin/dashboard/policies", json=policies)).status_code == 200
    await login(client, "alex")
    locked = by_key(await board(client))["health.services_summary"]
    item = {k: locked[k] for k in ("id", "widget_key", "x", "y", "w", "h")}
    refused = await client.put(
        "/api/v1/dashboard/arrangement", json={"items": [{**item, "x": (item["x"] + 4) % 8}]}
    )
    assert refused.status_code == 409 and refused.json()["code"] == "dashboard.policy_locked"
    assert refused.json()["widget"] == "health.services_summary"
    moved = await client.patch(f"/api/v1/dashboard/widgets/{locked['id']}", json={"x": 4})
    assert moved.status_code == 409


async def test_one_arrangement_per_screen(
    app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness
) -> None:
    """027: by default tablet and phone derive from the desktop arrangement; a member may arrange each screen
    on its own — switching starts every screen from what it showed — and a tablet arrangement leaves the
    desktop one untouched. A widget kept where it was dropped leaves its gap (free placement)."""
    register(dash)
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    await client.post("/api/v1/dashboard/widgets", json={"widget_key": "t.one"})
    view = await board(client)
    assert view["layout_mode"] == "shared" and all(i["views"] == {} for i in view["instances"])
    desktop = cells(view)
    switched = await client.put(
        "/api/v1/dashboard/layout-mode",
        json={"mode": "per_device"},
        headers={"If-Match": str(view["layout_version"])},
    )
    assert switched.status_code == 200
    view = await board(client)
    active = [i for i in view["instances"] if i["status"] == "active"]
    assert view["layout_mode"] == "per_device"
    assert all({"tablet", "phone"} <= set(i["views"]) for i in active)
    assert all(i["views"]["phone"]["x"] + i["views"]["phone"]["w"] <= 4 for i in active)
    moved = active[0]
    items = [{"id": i["id"], "widget_key": i["widget_key"], **i["views"]["tablet"]} for i in active]
    items[0].update(x=4, y=6, w=4, h=2)
    saved = await client.put(
        "/api/v1/dashboard/arrangement",
        params={"view": "tablet"},
        json={"items": items},
        headers={"If-Match": str(view["layout_version"])},
    )
    assert saved.status_code == 200
    after = await board(client)
    placed = next(i for i in after["instances"] if i["id"] == moved["id"])
    assert placed["views"]["tablet"] == {"x": 4, "y": 6, "w": 4, "h": 2}  # stays where it was put
    assert cells(after) == desktop  # the desktop arrangement did not change
    bad = await client.put("/api/v1/dashboard/layout-mode", json={"mode": "chaos"})
    assert bad.status_code == 422
    back = await client.put("/api/v1/dashboard/layout-mode", json={"mode": "shared"})
    assert back.status_code == 200
    assert all(i["views"] == {} for i in (await board(client))["instances"])  # shared: derived again
