"""025 T025 — alerts go through ``notifications.send_alert`` and are published as events usable by
Automations; diagnostics are descriptors pointing at the owners' APIs (with their permissions); executing
one goes through the owner, which audits it."""

from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.observability import SEND_ALERT, Alert
from tests.connectors_fixtures import admin_client
from tests.observability_fixtures import ObsHarness


class Notifications:
    def __init__(self) -> None:
        self.sent: list[Alert] = []

    async def send_alert(self, alert: Alert) -> None:
        self.sent.append(alert)


async def test_alerts_and_events(ob: ObsHarness) -> None:
    notifications = Notifications()
    ob.hl.cn.full.identity.capabilities.provide(SEND_ALERT, notifications, instance_ref="test", owner="test")
    service_id = await ob.hl.service()
    await ob.hl.module.runner.probe(service_id)
    ob.hl.cn.remote.fail_after = 0
    ob.hl.cn.remote.put("a", at=1)
    await ob.hl.cn.module.runner.run(UUID(service_id), kind="manual")
    await ob.module.cycle()
    await ob.module.cycle()  # still failing: no duplicate alert
    keys = [a.key for a in notifications.sent]
    assert keys.count(f"component:connector:{service_id}") == 1
    events = await ob.outbox("observability.alert_raised")
    assert any(e["component"] == f"connector:{service_id}" for e in events)
    from portalab.capabilities.events import default_event_types

    assert default_event_types.get("observability.alert_raised").automatable  # type: ignore[union-attr]


async def test_diagnostics_point_to_owner_apis(
    app: FastAPI, client: httpx.AsyncClient, ob: ObsHarness
) -> None:
    service_id = await ob.hl.service()
    await ob.module.cycle()
    await admin_client(app, client, ob.hl.cn)
    detail = (await client.get(f"/api/v1/admin/observability/components/connector:{service_id}")).json()
    by_key: dict[str, Any] = {d["key"]: d for d in detail["diagnostics"]}
    assert by_key["rerun_sync"] == {
        "key": "rerun_sync",
        "label": "Synchronize now",
        "method": "POST",
        "path": f"/api/v1/services/{service_id}/sync",
        "permission": "services.manage",
    }
    response = await client.post(
        by_key["test_connector"]["path"]
    )  # executed by Connectors, not Observability
    assert response.status_code == 200
    resync = await client.post(f"/api/v1/services/{service_id}/resync", json={"mode": "partial"})
    assert resync.status_code == 202
    async with ob.database.session() as session:
        audited = await session.scalar(
            text("SELECT count(*) FROM audit.audit_entries WHERE action = 'connector.resync_requested'")
        )
    assert audited == 1  # the owner audits its own action
