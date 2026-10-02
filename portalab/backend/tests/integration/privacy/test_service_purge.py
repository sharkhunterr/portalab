"""021 T028 — purge needs ``services.purge`` + a confirmation bound to the service; the job removes only
that service's data; audited; ``service.data_purged`` emitted; disconnecting never purges."""

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.service_data import CAPABILITY
from portalab.core.event_port import OutboxEvent
from portalab.core.jobs.models import Job
from portalab.modules.authz.models import AuditEntry
from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.privacy_fixtures import FullPlatform


class FakeConnectorData:
    def __init__(self) -> None:
        self.rows = {"plex-a": 7, "plex-b": 3}

    async def has_service(self, service_id: str) -> bool:
        return service_id in self.rows

    async def purge_service_data(self, service_id: str) -> int:
        return self.rows.pop(service_id, 0)


async def test_purge_flow(app: FastAPI, client: httpx.AsyncClient, full: FullPlatform) -> None:
    data = FakeConnectorData()
    full.identity.capabilities.provide(CAPABILITY, data, instance_ref="media", owner="test")
    admin_id = await create_user(module_of(app), "boss")
    await make_admin(full, admin_id)
    await create_user(module_of(app), "plain")

    await login(client, "plain")
    assert (await client.post("/api/v1/services/plex-a/purge", json={})).status_code == 403

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as boss:
        await login(boss, "boss")
        first = await boss.post("/api/v1/services/plex-a/purge", json={})
        assert first.status_code == 409 and first.json()["code"] == "authz.confirmation_required"
        token = first.json()["confirmation"]
        wrong = await boss.post("/api/v1/services/plex-b/purge", json={"confirmation": token})
        assert wrong.status_code == 403  # bound to plex-a (and now burnt)
        token = (await boss.post("/api/v1/services/plex-a/purge", json={})).json()["confirmation"]
        accepted = await boss.post("/api/v1/services/plex-a/purge", json={"confirmation": token})
        assert accepted.status_code == 202
    assert data.rows == {"plex-a": 7, "plex-b": 3}  # nothing purged until the job runs
    async with full.database.session() as session:
        assert (await session.execute(select(Job.kind))).scalars().all() == ["privacy.purge_service_data"]
    assert await full.privacy.purge.run("plex-a") == 7
    assert data.rows == {"plex-b": 3}
    async with full.database.session() as session:
        events = (await session.execute(select(OutboxEvent.type))).scalars().all()
        actions = (await session.execute(select(AuditEntry.action))).scalars().all()
    assert "service.data_purged" in events
    assert {"service.purge_requested", "service.data_purged"} <= set(actions)
