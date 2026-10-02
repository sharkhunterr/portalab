"""006 T018 — infrastructure metrics are per metric (``not available``, never zero; partial provider shows
the rest); operations need confirmation, are audited, and an unreachable host yields an actionable error."""

import httpx
from fastapi import FastAPI
from sqlalchemy import text

from tests.connectors_fixtures import admin_client
from tests.health_fixtures import HealthHarness


async def test_metrics_per_metric_availability(hl: HealthHarness) -> None:
    service_id = await hl.service()
    result = await hl.module.infra.fetch(service_id, ["cpu", "ram", "gpu"])
    assert result["state"] == "partial"
    assert result["metrics"]["cpu"] == {"available": True, "value": 12.5, "unit": "%"}
    assert result["metrics"]["gpu"] == {"available": False, "reason": "not reported by the host"}
    assert "value" not in result["metrics"]["gpu"]  # never a zero
    async with hl.cn.full.database.session() as session:
        rows = (
            await session.execute(
                text("SELECT metric, value, available FROM health.infra_samples ORDER BY metric")
            )
        ).all()
    assert [tuple(r) for r in rows] == [("cpu", 12.5, True), ("gpu", None, False), ("ram", 2048.0, True)]
    hl.cn.remote.mode = "error"
    down = await hl.module.infra.fetch(service_id, ["cpu"])
    assert down["state"] == "unavailable" and down["metrics"]["cpu"]["available"] is False


async def test_operations_confirmation_audit_and_errors(
    app: FastAPI, client: httpx.AsyncClient, hl: HealthHarness
) -> None:
    service_id = await hl.service()
    await admin_client(app, client, hl.cn)
    listing = await client.get(f"/api/v1/services/{service_id}/operations")
    assert listing.status_code == 200 and [o["key"] for o in listing.json()["items"]] == ["restart"]
    first = await client.post(f"/api/v1/services/{service_id}/operations/restart", json={})
    assert first.status_code == 409 and first.json()["code"] == "authz.confirmation_required"
    done = await client.post(
        f"/api/v1/services/{service_id}/operations/restart",
        json={"confirmation": first.json()["confirmation"]},
    )
    assert done.status_code == 200 and done.json()["result"] == {"restarted": True}
    assert hl.cn.remote.operations_run == ["restart"]

    hl.cn.remote.mode = "error"
    again = await client.get(f"/api/v1/services/{service_id}/operations")
    assert again.status_code == 503 and again.json()["code"] == "operation.failed"  # actionable listing error
    hl.cn.remote.mode = "ok"
    first = await client.post(f"/api/v1/services/{service_id}/operations/restart", json={})
    hl.cn.remote.mode = "error"
    hl.module.operations.list = _cached_listing  # type: ignore[method-assign]
    failed = await client.post(
        f"/api/v1/services/{service_id}/operations/restart",
        json={"confirmation": first.json()["confirmation"]},
    )
    assert failed.status_code == 503 and "reachable" in failed.json()["detail"]
    async with hl.cn.full.database.session() as session:
        outcomes = (
            (
                await session.execute(
                    text(
                        "SELECT result FROM audit.audit_entries WHERE action = 'service.operation_performed' "
                        "ORDER BY occurred_at"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert sorted(outcomes) == ["failure", "success"]
    assert len(await hl.outbox("service.operation_performed")) == 2


async def _cached_listing(service_id: str) -> list[dict[str, object]]:
    return [{"key": "restart", "label": "Restart", "description": "", "sensitive": True}]
