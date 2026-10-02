"""020 T017 — toggles write state + audit + event; data untouched; compatibility hook consulted before
enabling (a failing hook blocks); plugin permissions withdrawn and restored."""

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.administration import TOGGLE_HOOK_CAPABILITY
from portalab.core.event_port import OutboxEvent
from portalab.core.permissions import default_permissions
from portalab.modules.authz.models import AuditEntry, Permission
from tests.authz_fixtures import make_admin, user
from tests.integration.identity.helpers import create_user, login, module_of
from tests.privacy_fixtures import FullPlatform


class Hook:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.block = False

    async def check_enable(self, kind: str, ref: str) -> list[str]:
        self.calls.append((kind, ref))
        return ["requires portalab >= 2.0"] if self.block else []


async def test_toggle_flow(app: FastAPI, client: httpx.AsyncClient, full: FullPlatform) -> None:
    hook = Hook()
    full.identity.capabilities.provide(TOGGLE_HOOK_CAPABILITY, hook, instance_ref="test", owner="test")
    default_permissions.declare("plugin:weather.use", "Weather", owner="plugin:weather", user_grantable=True)
    try:
        full.authz.catalog.invalidate()
        await full.authz.catalog.ensure()
        admin_id = await create_user(module_of(app), "boss")
        await make_admin(full, admin_id)
        await login(client, "boss")
        off = await client.post(
            "/api/v1/admin/toggles/plugin/weather", json={"enabled": False, "reason": "maintenance"}
        )
        assert off.status_code == 200 and off.json()["enabled"] is False
        async with full.database.session() as session:
            assert (await session.get(Permission, "plugin:weather.use")).enabled is False  # type: ignore[union-attr]
        assert hook.calls == []  # hooks only gate enabling
        hook.block = True
        refused = await client.post("/api/v1/admin/toggles/plugin/weather", json={"enabled": True})
        assert refused.status_code == 409 and refused.json()["code"] == "admin.enable_refused"
        hook.block = False
        on = await client.post("/api/v1/admin/toggles/plugin/weather", json={"enabled": True})
        assert on.json()["enabled"] is True
        async with full.database.session() as session:
            assert (await session.get(Permission, "plugin:weather.use")).enabled is True  # type: ignore[union-attr]
            events = (await session.execute(select(OutboxEvent.type))).scalars().all()
            audits = (await session.execute(select(AuditEntry.action))).scalars().all()
        assert events.count("admin.plugin_toggled") == 2 and audits.count("admin.plugin_toggled") == 2
        assert await full.administration.toggles.is_enabled("plugin", "weather")
        assert await full.administration.toggles.is_enabled("module", "never-toggled")  # default: enabled
        await create_user(module_of(app), "plain")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
        ) as plain:
            await login(plain, "plain")
            assert (
                await plain.post("/api/v1/admin/toggles/module/x", json={"enabled": False})
            ).status_code == 403
        assert user(admin_id)
    finally:
        default_permissions.unregister("plugin:weather")
