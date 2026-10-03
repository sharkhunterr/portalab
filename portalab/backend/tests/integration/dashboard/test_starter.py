"""009 T025 — the starter dashboard is applied once (idempotent), filtered by permission and policy (and
roles); a broken starter entry never blocks the others; the user personalizes afterwards; ``default``
widgets join the starter; the onboarding ``dashboard`` step can then be completed."""

from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI

from portalab.core.authz_port import Principal
from tests.integration.dashboard.conftest import DashboardHarness
from tests.integration.identity.helpers import create_user, login, module_of
from tests.unit.dashboard.fakes import FakeWidget, definition

pytestmark = pytest.mark.integration


async def test_starter(app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness) -> None:
    dash.registry.register(definition("t.secret", required_permission="audit.read"), FakeWidget())
    dash.registry.register(definition("t.default"), FakeWidget())
    dash.registry.register(definition("t.editors"), FakeWidget())
    dash.module.config = replace(
        dash.module.config,
        widget_policies={"t.default": {"class": "default"}},
        starter_layout=[
            {"widget_key": "health.services_summary", "w": 6, "h": 2},
            {"widget_key": "t.secret", "w": 4, "h": 2},
            {"widget_key": "t.editors", "w": 4, "h": 2, "roles": ["editor"]},
            {"widget_key": "t.gone", "w": 4, "h": 2},
            {"widget_key": "dashboard.welcome", "w": "not-a-number"},
        ],
    )
    user = await create_user(module_of(app), "alex")
    principal = Principal(user_id=user)
    assert await dash.module.service.apply_starter(principal) is True
    assert await dash.module.service.apply_starter(principal) is False  # idempotent
    await login(client, "alex")
    keys = [i["widget_key"] for i in (await client.get("/api/v1/dashboard")).json()["instances"]]
    assert keys == ["health.services_summary", "t.default"]
    assert (await client.post("/api/v1/dashboard/starter")).json() == {"applied": False}
    assert (
        await client.post("/api/v1/dashboard/widgets", json={"widget_key": "dashboard.welcome"})
    ).status_code == 201
    identity = module_of(app)
    async with identity.ctx.database.unit_of_work() as uow:
        await identity.onboarding.start(uow.session, user, identity.ctx.now())
    assert (await client.post("/api/v1/me/onboarding/dashboard/complete")).status_code == 200
