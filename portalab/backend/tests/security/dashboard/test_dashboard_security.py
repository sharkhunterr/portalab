"""009 T003/T036 — route permissions; instances only reachable by their owner; dashboard data exported
and erased with the account (privacy participants); events carry counts only."""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from tests.integration.dashboard.conftest import DashboardHarness
from tests.integration.identity.helpers import create_user, login, module_of

pytestmark = pytest.mark.integration


async def test_matrix(app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness) -> None:
    routes = [
        ("GET", "/api/v1/dashboard"),
        ("GET", "/api/v1/dashboard/catalog"),
        ("POST", "/api/v1/dashboard/widgets"),
        ("PATCH", "/api/v1/dashboard/widgets/00000000-0000-7000-8000-000000000001"),
        ("DELETE", "/api/v1/dashboard/widgets/00000000-0000-7000-8000-000000000001"),
        ("PUT", "/api/v1/dashboard/layout"),
        ("POST", "/api/v1/dashboard/starter"),
        ("GET", "/api/v1/widgets/dashboard.welcome/data"),
        ("GET", "/api/v1/dashboard/since-last-login"),
        ("POST", "/api/v1/dashboard/since-last-login/seen"),
        ("GET", "/api/v1/admin/dashboard/policies"),
        ("PUT", "/api/v1/admin/dashboard/policies"),
        ("GET", "/api/v1/admin/dashboard/starter"),
        ("PUT", "/api/v1/admin/dashboard/starter"),
    ]
    for method, path in routes:
        assert (await client.request(method, path, json={})).status_code == 401, path
    await create_user(module_of(app), "plain")
    await login(client, "plain")
    for method, path in routes[-4:]:
        assert (await client.request(method, path, json={})).status_code == 403, path


async def test_export_erase_and_events(
    app: FastAPI, client: httpx.AsyncClient, dash: DashboardHarness
) -> None:
    alex = await create_user(module_of(app), "alex")
    await login(client, "alex")
    await client.get("/api/v1/dashboard")
    capabilities = dash.full.identity.capabilities
    [exporter] = [
        p.provider for p in capabilities.system_providers(EXPORT_CAPABILITY) if p.instance_ref == "dashboard"
    ]
    records = await exporter.export(alex)
    # the starter widgets this member can use (027 starter)
    assert {r.data["widget"] for r in records} == {
        "dashboard.since_last_visit",
        "dashboard.welcome",
        "health.services_summary",
        "health.service_links",
    }
    async with dash.full.database.session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT type, metadata::text FROM core.event_outbox "
                    "WHERE type LIKE 'dashboard.%' ORDER BY type"
                )
            )
        ).all()
    assert [r[0] for r in rows] == ["dashboard.layout_changed", "dashboard.starter_applied"]
    assert all(str(alex) not in r[1] for r in rows)
    [eraser] = [
        p.provider for p in capabilities.system_providers(ERASURE_CAPABILITY) if p.instance_ref == "dashboard"
    ]
    await eraser.erase(alex, "final")
    await eraser.erase(alex, "final")
    assert await exporter.export(alex) == []
