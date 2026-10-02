"""020 T026 — modules register their admin surfaces; the Control Center lists only permitted ones; a removed
(disabled) owner's surfaces disappear."""

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.administration import AdminSurface, default_admin_surfaces
from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.privacy_fixtures import FullPlatform

pytestmark = pytest.mark.integration


async def test_surfaces(app: FastAPI, client: httpx.AsyncClient, full: FullPlatform) -> None:
    keys = {surface.key for surface in default_admin_surfaces.all()}
    assert {"configuration", "extensions", "users", "roles", "audit", "privacy"} <= keys
    default_admin_surfaces.register(
        AdminSurface("weather", "w", "/admin/weather", "plugins.manage", "plugin:weather")
    )
    admin_id = await create_user(module_of(app), "boss")
    await make_admin(full, admin_id)
    await login(client, "boss")
    assert "weather" in {s["key"] for s in (await client.get("/api/v1/admin/surfaces")).json()}
    assert default_admin_surfaces.unregister("plugin:weather") == 1
    assert "weather" not in {s["key"] for s in (await client.get("/api/v1/admin/surfaces")).json()}
    await create_user(module_of(app), "plain")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as plain:
        await login(plain, "plain")
        assert (await plain.get("/api/v1/admin/surfaces")).json() == []
