"""005 T039 — connectors routes: anonymous 401; a plain user (``services.read`` only) sees names and states
but no configuration and gets 403 on every management route; the Admin gets through; logs and metrics
never carry credentials."""

import logging

import httpx
import pytest
from fastapi import FastAPI

from portalab.modules.connectors.observability import metrics
from tests.connectors_fixtures import TOKEN, ConnectorsHarness, admin_client
from tests.integration.identity.helpers import create_user, login, module_of

pytestmark = pytest.mark.integration
SID = "00000000-0000-7000-8000-000000000000"
MANAGE_ROUTES = [
    ("POST", "/api/v1/services"),
    ("PATCH", f"/api/v1/services/{SID}"),
    ("POST", f"/api/v1/services/{SID}/test"),
    ("POST", "/api/v1/connectors/fake/test"),
    ("POST", f"/api/v1/services/{SID}/enable"),
    ("POST", f"/api/v1/services/{SID}/disable"),
    ("POST", f"/api/v1/services/{SID}/disconnect"),
    ("POST", f"/api/v1/services/{SID}/sync"),
    ("POST", f"/api/v1/services/{SID}/resync"),
    ("POST", "/api/v1/connectors/fake/discover"),
    ("GET", "/api/v1/discovery"),
    ("POST", f"/api/v1/discovery/{SID}/confirm"),
    ("POST", f"/api/v1/discovery/{SID}/decline"),
]
READ_ROUTES = [("GET", "/api/v1/connectors"), ("GET", "/api/v1/services")]


async def test_matrix(app: FastAPI, client: httpx.AsyncClient, cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    for method, path in [*MANAGE_ROUTES, *READ_ROUTES]:
        assert (await client.request(method, path, json={})).status_code == 401, path
    await create_user(module_of(app), "plain")
    await login(client, "plain")
    for method, path in MANAGE_ROUTES:
        assert (await client.request(method, path, json={})).status_code == 403, path
    listing = await client.get("/api/v1/services")
    assert listing.status_code == 200
    [item] = listing.json()["items"]
    assert item["state"] == "enabled" and "config" not in item and cn.base_url not in listing.text
    detail = await client.get(f"/api/v1/services/{service_id}")
    assert detail.status_code == 200 and "config" not in detail.json()


async def test_admin_sees_details(app: FastAPI, client: httpx.AsyncClient, cn: ConnectorsHarness) -> None:
    service_id = await cn.enabled()
    await admin_client(app, client, cn)
    detail = await client.get(f"/api/v1/services/{service_id}")
    assert detail.json()["config"]["base_url"] == cn.base_url and TOKEN not in detail.text


async def test_logs_and_metrics_hold_no_secrets(
    cn: ConnectorsHarness, caplog: pytest.LogCaptureFixture
) -> None:
    metrics.reset()
    caplog.set_level(logging.DEBUG)
    service_id = await cn.enabled()
    cn.remote.mode = "error"
    await cn.module.tester.test_service(service_id)
    await cn.module.runner.run(service_id, kind="manual")
    cn.remote.mode = "ok"
    await cn.module.runner.run(service_id, kind="manual")
    snapshot = metrics.snapshot()
    assert snapshot["connectors.sync.failed"] == 1 and snapshot["connectors.sync.succeeded"] == 1
    text = " ".join(snapshot) + caplog.text
    assert TOKEN not in text and cn.base_url not in text
