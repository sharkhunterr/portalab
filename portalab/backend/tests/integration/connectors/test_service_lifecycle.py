"""005 T010 — configured → enabled → disabled → enabled → disconnected, events, credentials never returned."""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.modules.connectors.services.common import InvalidTransition
from tests.connectors_fixtures import TOKEN, ConnectorsHarness, admin_client


async def test_state_machine_and_events(cn: ConnectorsHarness) -> None:
    manager = cn.module.manager
    service_id = await cn.configure()
    assert (await manager.get(service_id)).state == "configured"
    assert (await manager.enable(cn.admin, service_id)).state == "enabled"
    assert (await manager.disable(cn.admin, service_id)).state == "disabled"
    assert (await manager.enable(cn.admin, service_id)).state == "enabled"
    view = await manager.disconnect(cn.admin, service_id)
    assert view.state == "disconnected" and view.historical and view.secrets_set == []
    with pytest.raises(InvalidTransition):
        await manager.enable(cn.admin, service_id)
    events = await cn.outbox("service.")
    assert [(e["type"], e["to_state"]) for e in events] == [
        ("service.connected", "enabled"),
        ("service.status_changed", "disabled"),
        ("service.connected", "enabled"),
        ("service.disconnected", "disconnected"),
    ]
    assert [e["state_seq"] for e in events] == [1, 2, 3, 4]
    async with cn.full.database.session() as session:
        audited = (
            await session.execute(
                text("SELECT action FROM audit.audit_entries WHERE resource_id = :id ORDER BY occurred_at"),
                {"id": str(service_id)},
            )
        ).scalars()
        assert "service.disconnected" in set(audited)


async def test_credentials_are_encrypted_and_never_returned(
    app: FastAPI, client: httpx.AsyncClient, cn: ConnectorsHarness
) -> None:
    await admin_client(app, client, cn)
    created = await client.post(
        "/api/v1/services",
        json={
            "connector": "fake",
            "name": "Media",
            "config": {"base_url": cn.base_url},
            "secrets": {"api_token": TOKEN},
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["secrets_set"] == ["api_token"] and TOKEN not in created.text
    service_id = body["id"]
    for response in (
        await client.get("/api/v1/services"),
        await client.get(f"/api/v1/services/{service_id}"),
        await client.post(f"/api/v1/services/{service_id}/enable"),
    ):
        assert response.status_code == 200, response.text
        assert TOKEN not in response.text
    async with cn.full.database.session() as session:
        stored = await session.scalar(
            text("SELECT credentials::text FROM connectors.services WHERE id = :id"), {"id": service_id}
        )
    assert stored is not None and TOKEN not in stored and "v1:" in stored
    assert (await client.post(f"/api/v1/services/{service_id}/disconnect")).json()["state"] == "disconnected"


async def test_unknown_secret_field_and_bad_config_rejected(cn: ConnectorsHarness) -> None:
    from portalab.modules.connectors.services.common import InvalidServiceConfig

    with pytest.raises(InvalidServiceConfig):
        await cn.module.manager.configure(cn.admin, connector_key="fake", name="x", config={})
    with pytest.raises(InvalidServiceConfig):
        await cn.module.manager.configure(
            cn.admin, connector_key="fake", name="x", config={"base_url": "http://x"}, secrets={"other": "v"}
        )


async def test_public_address_is_set_validated_cleared_and_offered(
    app: FastAPI, client: httpx.AsyncClient, cn: ConnectorsHarness
) -> None:
    """027 — the address members open a service at (the quick-access widget): set by an administrator, only
    http(s), cleared with an empty value; without one, an https connection address is offered, never a plain
    http one."""
    from portalab.modules.connectors.directory import ConnectorServiceDirectory

    await admin_client(app, client, cn)
    created = await client.post(
        "/api/v1/services",
        json={"connector": "fake", "name": "Media", "config": {"base_url": cn.base_url}, "secrets": {}},
    )
    service_id = created.json()["id"]
    directory = ConnectorServiceDirectory(cn.module.manager)
    assert (await directory.service(service_id)).link is None  # type: ignore[union-attr]  # plain http
    bad = await client.patch(f"/api/v1/services/{service_id}", json={"public_url": "javascript:alert(1)"})
    assert bad.status_code == 422
    set_ = await client.patch(f"/api/v1/services/{service_id}", json={"public_url": "https://media.example"})
    assert set_.status_code == 200 and set_.json()["public_url"] == "https://media.example"
    assert (await directory.service(service_id)).link == "https://media.example"  # type: ignore[union-attr]
    cleared = await client.patch(f"/api/v1/services/{service_id}", json={"public_url": ""})
    assert cleared.status_code == 200 and cleared.json()["public_url"] is None

    # 027: importance and the service's own alerting overrides (left-out fields follow the importance)
    alerting = {"incident": False, "email_admins": True, "notify_after": 0}
    tuned = await client.patch(
        f"/api/v1/services/{service_id}", json={"importance": "critical", "alerting": alerting}
    )
    assert tuned.status_code == 200 and tuned.json()["alerting"] == alerting
    info = await directory.service(service_id)
    assert info is not None and info.importance == "critical" and info.alerting == alerting
    wrong = await client.patch(f"/api/v1/services/{service_id}", json={"alerting": {"incident_after": 0}})
    assert wrong.status_code == 422
    reset = await client.patch(f"/api/v1/services/{service_id}", json={"alerting": {}})
    assert reset.json()["alerting"] == {}
