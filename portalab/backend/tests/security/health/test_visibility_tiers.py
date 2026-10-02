"""006 T017/T025/T026 — permission tiers enforced server side: a standard user gets state and availability
only; ``infrastructure.read`` adds metrics and errors; ``services.manage`` adds operations. Anonymous 401,
management routes 403 for standard users; metrics and logs carry no secrets or hosts."""

import logging

import httpx
import pytest
from fastapi import FastAPI

from portalab.modules.health.observability import metrics
from tests.connectors_fixtures import TOKEN, admin_client
from tests.health_fixtures import HealthHarness
from tests.integration.identity.helpers import create_user, login, module_of

pytestmark = pytest.mark.integration
SID = "00000000-0000-7000-8000-000000000000"
MANAGE = [
    ("POST", "/api/v1/maintenance"),
    ("PATCH", f"/api/v1/maintenance/{SID}"),
    ("DELETE", f"/api/v1/maintenance/{SID}"),
    ("GET", f"/api/v1/services/{SID}/operations"),
    ("POST", f"/api/v1/services/{SID}/operations/restart"),
]
READ = [
    ("GET", "/api/v1/services/health"),
    ("GET", f"/api/v1/services/{SID}/health"),
    ("GET", f"/api/v1/services/{SID}/health/history"),
    ("GET", "/api/v1/maintenance"),
    ("GET", f"/api/v1/services/{SID}/maintenance"),
]


async def test_matrix_and_tiers(app: FastAPI, client: httpx.AsyncClient, hl: HealthHarness) -> None:
    service_id = await hl.service()
    await hl.module.runner.probe(service_id)
    for method, path in [*MANAGE, *READ]:
        assert (await client.request(method, path, json={})).status_code == 401, path

    identity = module_of(app)
    await create_user(identity, "plain")
    helper_id = await create_user(identity, "helper")
    await hl.cn.full.authz.grants.assign_role(
        hl.cn.admin, helper_id, "support"
    )  # support ⇒ infrastructure.read

    await login(client, "plain")
    for method, path in MANAGE:
        assert (await client.request(method, path, json={})).status_code == 403, path
    overview = await client.get("/api/v1/services/health")
    assert overview.status_code == 200 and overview.json()["items"][0]["state"] == "operational"
    standard = (await client.get(f"/api/v1/services/{service_id}/health")).json()["sections"]
    assert set(standard) == {"state", "availability", "maintenance", "incidents", "sync", "history"}
    assert set(standard["state"]["data"]) == {"state", "since"}
    assert set(standard["availability"]["data"]) == {"availability", "window_hours"}
    history = (await client.get(f"/api/v1/services/{service_id}/health/history")).json()
    assert "metrics" not in history and "errors" not in history

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as other:
        await login(other, "helper")
        infra = (await other.get(f"/api/v1/services/{service_id}/health")).json()["sections"]
        assert {"errors", "tickets", "infrastructure"} <= set(infra) and "operations" not in infra
        assert "last_check_at" in infra["state"]["data"]
        assert (await other.get(f"/api/v1/services/{service_id}/operations")).status_code == 403
        assert "metrics" in (await other.get(f"/api/v1/services/{service_id}/health/history")).json()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as boss:
        await admin_client(app, boss, hl.cn)
        full = (await boss.get(f"/api/v1/services/{service_id}/health")).json()["sections"]
        assert "operations" in full


async def test_unknown_service_and_bad_range(
    app: FastAPI, client: httpx.AsyncClient, hl: HealthHarness
) -> None:
    await admin_client(app, client, hl.cn)
    assert (await client.get(f"/api/v1/services/{SID}/health")).status_code == 404
    service_id = await hl.service()
    bad = await client.get(
        f"/api/v1/services/{service_id}/health/history",
        params={"from": "2026-10-02T00:00:00Z", "to": "2026-10-01T00:00:00Z"},
    )
    assert bad.status_code == 422 and bad.json()["code"] == "health.invalid_range"


async def test_metrics_and_logs_redacted(hl: HealthHarness, caplog: pytest.LogCaptureFixture) -> None:
    metrics.reset()
    caplog.set_level(logging.DEBUG)
    service_id = await hl.service()
    await hl.module.runner.probe(service_id)
    hl.cn.remote.mode = "error"
    await hl.module.runner.probe(service_id)
    snapshot = metrics.snapshot()
    assert snapshot["health.probes.ok"] == 1 and snapshot["health.probes.failed"] == 1
    text = " ".join(snapshot) + caplog.text
    assert TOKEN not in text and hl.cn.base_url not in text
