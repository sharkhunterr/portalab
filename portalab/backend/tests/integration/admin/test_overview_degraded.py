"""020 T023/T029 — panels load independently: a slow or failing provider is ``unavailable`` alone; panels and
required actions are filtered by permission; actions sorted actionable → impact → criticality → age; the
built-in configuration and audit panels and the placeholders of not-yet-installed domains."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import FastAPI

from portalab.capabilities.administration import (
    PANEL_CAPABILITY,
    REQUIRED_ACTION_CAPABILITY,
    PanelResult,
    RequiredAction,
)
from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.privacy_fixtures import FullPlatform

T0 = datetime(2026, 10, 1, tzinfo=UTC)


class Slow:
    async def panel(self, principal: object) -> PanelResult:
        await asyncio.sleep(5)
        return PanelResult("available")


class Broken:
    async def panel(self, principal: object) -> PanelResult:
        raise RuntimeError("provider crashed")


class Fine:
    async def panel(self, principal: object) -> PanelResult:
        return PanelResult("available", {"tickets_open": 3})


class Actions:
    async def items(self, principal: object) -> list[RequiredAction]:
        return [
            RequiredAction("old-low", "a", impact=1, criticality=1, since=T0, link="/x"),
            RequiredAction("big", "b", impact=5, criticality=1, since=T0 + timedelta(days=1), link="/y"),
            RequiredAction("info", "c", impact=9, criticality=9, since=T0, link="/z", actionable=False),
            RequiredAction("critical", "d", impact=5, criticality=4, since=T0 + timedelta(days=2), link="/w"),
        ]


async def test_overview(app: FastAPI, client: httpx.AsyncClient, full: FullPlatform) -> None:
    caps = full.identity.capabilities
    full.administration.control_center.timeout = 0.2
    for name, provider, permission in (
        ("slow", Slow(), None),
        ("broken", Broken(), None),
        ("support", Fine(), "tickets.manage"),
        ("public", Fine(), None),
    ):
        caps.provide(
            PANEL_CAPABILITY,
            provider,
            instance_ref=f"test.{name}",
            owner="test",
            metadata={"panel": name, "permission": permission, "order": 90},
        )
    caps.provide(
        REQUIRED_ACTION_CAPABILITY,
        Actions(),
        instance_ref="test",
        owner="test",
        metadata={"permission": "configuration.manage"},
    )
    admin_id = await create_user(module_of(app), "boss")
    await make_admin(full, admin_id)
    await create_user(module_of(app), "plain")

    await login(client, "boss")
    started = asyncio.get_running_loop().time()
    body = (await client.get("/api/v1/admin/overview")).json()
    assert asyncio.get_running_loop().time() - started < 2  # the slow panel did not block the others
    states = {panel["panel"]: panel["state"] for panel in body["panels"]}
    assert states["slow"] == "unavailable" and states["broken"] == "unavailable"
    assert states["public"] == "available" and states["support"] == "available"
    assert states["configuration"] in ("available", "partial")
    assert states["health"] == "unavailable" and states["audit"] == "available"
    assert [action["id"] for action in body["required_actions"]] == ["critical", "big", "old-low", "info"]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as plain:
        await login(plain, "plain")
        mine = (await plain.get("/api/v1/admin/overview")).json()
    assert {panel["panel"] for panel in mine["panels"]} == {"slow", "broken", "public"}
    assert mine["required_actions"] == []
