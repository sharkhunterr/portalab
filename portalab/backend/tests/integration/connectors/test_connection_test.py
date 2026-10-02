"""005 T014 — connection test: actionable pass/fail diagnostics, never changes state, secrets redacted."""

import httpx
from fastapi import FastAPI

from tests.connectors_fixtures import TOKEN, ConnectorsHarness, admin_client


async def test_pass_and_fail_without_state_change(cn: ConnectorsHarness) -> None:
    service_id = await cn.configure()
    ok = await cn.module.tester.test_service(service_id)
    assert ok.ok and ok.reachable and ok.authenticated
    cn.remote.mode = "error"
    down = await cn.module.tester.test_service(service_id)
    assert not down.ok and not down.reachable and "check the address" in down.detail
    cn.remote.mode = "auth_error"
    rejected = await cn.module.tester.test_service(service_id)
    assert not rejected.ok and rejected.reachable and not rejected.authenticated
    cn.remote.mode = "hang"
    slow = await cn.module.tester.test_service(service_id)
    assert not slow.ok and "in time" in slow.detail
    assert (await cn.module.manager.get(service_id)).state == "configured"


async def test_wrong_token_and_draft_override(cn: ConnectorsHarness) -> None:
    service_id = await cn.configure(token="wrong-token-value")
    assert not (await cn.module.tester.test_service(service_id)).authenticated
    fixed = await cn.module.tester.test_service(service_id, secrets={"api_token": TOKEN})
    assert fixed.ok  # draft overrides are not persisted
    assert not (await cn.module.tester.test_service(service_id)).ok


async def test_api_test_is_redacted(app: FastAPI, client: httpx.AsyncClient, cn: ConnectorsHarness) -> None:
    await admin_client(app, client, cn)
    draft = await client.post(
        "/api/v1/connectors/fake/test",
        json={"config": {"base_url": cn.base_url}, "secrets": {"api_token": TOKEN}},
    )
    assert draft.status_code == 200 and draft.json()["ok"] is True and TOKEN not in draft.text
    service_id = await cn.configure()
    cn.remote.mode = "error"
    failed = await client.post(f"/api/v1/services/{service_id}/test")
    assert failed.status_code == 200 and failed.json()["ok"] is False and TOKEN not in failed.text
    refused = await client.post(f"/api/v1/services/{service_id}/enable")
    assert refused.status_code == 409 and refused.json()["code"] == "connector.test_failed"
    assert (await cn.module.manager.get(service_id)).state == "configured"
