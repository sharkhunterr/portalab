"""009 T030/T037/T034 — plugin/marketplace widgets are declarative (standard template), namespaced, appear
in the catalog at once, follow the same permissions/states/policies; string settings refuse markup;
disabling the plugin keeps users' instances as placeholders (config retained) restored on reactivation;
widget products need an entitlement (015 stub); invalidation events become ``widget.invalidate`` live
messages (key only, duplicates harmless)."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.dashboard import ENTITLEMENTS
from portalab.modules.dashboard.invalidate.bridge import invalidation_consumer
from portalab.modules.dashboard.registry.plugin_widgets import plugin_state_consumer, register_plugin_widget
from tests.integration.dashboard.conftest import DashboardHarness
from tests.integration.identity.helpers import create_user, login, module_of
from tests.unit.dashboard.fakes import FakeWidget, definition

pytestmark = pytest.mark.integration

MANIFEST: Mapping[str, Any] = {
    "name": "now_playing",
    "template": "stat",
    "permission": "users.self.manage",
    "config_schema": {"type": "object", "properties": {"label": {"type": "string"}}},
    "config_defaults": {"label": "Now"},
    "invalidate_on": ["radio.track_changed"],
}


class Envelope:
    def __init__(self, type_: str, payload: dict[str, Any]) -> None:
        self.type = type_
        self.payload = payload
        self.event_id = uuid4()


class Ctx:
    replay = False


async def test_plugin_widget_lifecycle(
    app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness
) -> None:
    widget = FakeWidget("crash")
    definition = register_plugin_widget(dash.registry, "radio", MANIFEST, widget)
    assert definition.key == "plugin:radio.now_playing"
    await create_user(module_of(app), "alex")
    await login(client, "alex")
    assert definition.key in {c["key"] for c in (await client.get("/api/v1/dashboard/catalog")).json()}
    xss = await client.post(
        "/api/v1/dashboard/widgets",
        json={"widget_key": definition.key, "config": {"label": "<script>x</script>"}},
    )
    assert xss.status_code == 422 and xss.json()["code"] == "dashboard.config_invalid"
    created = await client.post(
        "/api/v1/dashboard/widgets", json={"widget_key": definition.key, "config": {"label": "Live"}}
    )
    instance = created.json()["id"]
    assert (await client.get(f"/api/v1/widgets/{definition.key}/data")).json()[
        "state"
    ] == "error"  # isolated failure

    await plugin_state_consumer(dash.registry).handler(
        Envelope("plugin.state_changed", {"plugin_id": "radio", "state": "disabled"}), Ctx()
    )  # type: ignore[arg-type]
    placeholder = next(
        i
        for i in (await client.get("/api/v1/dashboard")).json()["instances"]
        if i["widget_key"] == definition.key
    )
    assert (
        placeholder["available"] is False
        and placeholder["widget"] is None
        and placeholder["config"] == {"label": "Live"}
    )
    assert (await client.get(f"/api/v1/widgets/{definition.key}/data")).status_code == 404
    register_plugin_widget(dash.registry, "radio", MANIFEST, FakeWidget())
    back = next(i for i in (await client.get("/api/v1/dashboard")).json()["instances"] if i["id"] == instance)
    assert back["available"] is True and back["config"] == {"label": "Live"}

    consumer = invalidation_consumer(dash.full.database, dash.registry, frozenset({"radio.track_changed"}))
    for _ in range(2):  # duplicates are harmless
        await consumer.handler(Envelope("radio.track_changed", {"track": "x"}), Ctx())  # type: ignore[arg-type]
    async with dash.full.database.session() as session:
        rows = (
            await session.execute(
                text("SELECT topic, payload::text FROM core.live_event WHERE topic = 'widget.invalidate'")
            )
        ).all()
    assert rows and all(row[1] == '{"widget": "plugin:radio.now_playing"}' for row in rows)


class Entitlements:
    def __init__(self, owners: set[UUID]) -> None:
        self.owners = owners

    async def owns(self, user_id: UUID, product: str) -> bool:
        return user_id in self.owners and product == "widget.weather"


async def test_widget_products_need_an_entitlement(
    app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness
) -> None:
    register_plugin_widget(
        dash.registry, "weather", {**MANIFEST, "name": "today", "product": "widget.weather"}, FakeWidget()
    )
    key = "plugin:weather.today"
    buyer = await create_user(module_of(app), "buyer")
    await create_user(module_of(app), "other")
    await login(client, "buyer")
    gallery = (await client.get("/api/v1/dashboard/catalog")).json()
    # 027: a product widget not owned shows as « in the shop » (locked), never as addable
    assert {c["key"]: c["locked"] for c in gallery}[key] is True
    dash.full.identity.capabilities.provide(
        ENTITLEMENTS, Entitlements({buyer}), instance_ref="t", owner="module:marketplace"
    )
    gallery = (await client.get("/api/v1/dashboard/catalog")).json()
    assert {c["key"]: c["locked"] for c in gallery}[key] is False
    assert (await client.get(f"/api/v1/widgets/{key}/data")).json()["state"] == "available"
    await login(client, "other")
    gallery = (await client.get("/api/v1/dashboard/catalog")).json()
    assert {c["key"]: c["locked"] for c in gallery}[key] is True
    assert (await client.get(f"/api/v1/widgets/{key}/data")).json()["state"] == "unauthorized"


class _Shop:
    """027: the Marketplace cosmetics port — an existing widget and a widget setting sold in the shop."""

    def __init__(self, owners: set[UUID]) -> None:
        self.owners = owners

    async def sold(self, kind: str, field: str) -> frozenset[str]:
        return frozenset(
            {"t.sold"} if kind == "widget" else {"t.sold:limit=9"} if kind == "widget_option" else set()
        )

    async def owned(self, user_id: UUID, kind: str, field: str) -> frozenset[str]:
        if user_id not in self.owners:
            return frozenset()
        return await self.sold(kind, field)

    async def equipped(self, user_id: UUID) -> dict[str, object]:
        return {}


async def test_existing_widgets_and_settings_sold_in_the_shop(
    app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness
) -> None:
    from portalab.capabilities.themes import COSMETICS

    dash.registry.register(definition("t.sold"), FakeWidget())
    buyer = await create_user(module_of(app), "buyer")
    await create_user(module_of(app), "other")
    dash.full.identity.capabilities.provide(
        COSMETICS, _Shop({buyer}), instance_ref="t", owner="module:marketplace"
    )
    await login(client, "other")
    gallery = {c["key"]: c["locked"] for c in (await client.get("/api/v1/dashboard/catalog")).json()}
    assert gallery["t.sold"] is True  # sold: shown « in the shop », never addable
    assert (await client.get("/api/v1/widgets/t.sold/data")).json()["state"] == "unauthorized"
    await login(client, "buyer")
    gallery = {c["key"]: c["locked"] for c in (await client.get("/api/v1/dashboard/catalog")).json()}
    assert gallery["t.sold"] is False
    added = await client.post(
        "/api/v1/dashboard/widgets", json={"widget_key": "t.sold", "config": {"limit": 9}}
    )
    assert added.status_code == 201, added.text  # the buyer owns the setting too
    await login(client, "other")
    assert (await client.get("/api/v1/dashboard/locked-options")).json() == {"locked": ["t.sold:limit=9"]}


class _StaffShop(_Shop):
    async def sold(self, kind: str, field: str) -> frozenset[str]:
        return frozenset(
            {"t.staff"} if kind == "widget" else {"t.staff:limit=9"} if kind == "widget_option" else set()
        )


async def test_a_widget_sold_to_members_is_the_staffs_own(
    app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#53: a widget about the servers — sold to members (often with a contribution minimum), given with
    its sold settings to the holders of a permission (the administrators)."""
    from dataclasses import replace

    from portalab.capabilities.themes import COSMETICS

    dash.registry.register(replace(definition("t.staff"), free_with="staff.perm"), FakeWidget())
    staff = await create_user(module_of(app), "staff")
    await create_user(module_of(app), "member")
    dash.full.identity.capabilities.provide(
        COSMETICS, _StaffShop(set()), instance_ref="t", owner="module:marketplace"
    )
    authorizer = dash.module.service.gateway.authorizer
    original = authorizer.is_allowed

    async def is_allowed(principal, permission, *args, **kwargs):  # type: ignore[no-untyped-def]
        if permission == "staff.perm":
            return principal.user_id == staff
        return await original(principal, permission, *args, **kwargs)

    monkeypatch.setattr(authorizer, "is_allowed", is_allowed)
    await login(client, "member")
    gallery = {c["key"]: c["locked"] for c in (await client.get("/api/v1/dashboard/catalog")).json()}
    assert gallery["t.staff"] is True  # in the shop for a member
    assert (await client.get("/api/v1/dashboard/locked-options")).json() == {"locked": ["t.staff:limit=9"]}
    await login(client, "staff")
    gallery = {c["key"]: c["locked"] for c in (await client.get("/api/v1/dashboard/catalog")).json()}
    assert gallery["t.staff"] is False
    assert (await client.get("/api/v1/dashboard/locked-options")).json() == {"locked": []}
    added = await client.post(
        "/api/v1/dashboard/widgets", json={"widget_key": "t.staff", "config": {"limit": 9}}
    )
    assert added.status_code == 201, added.text
