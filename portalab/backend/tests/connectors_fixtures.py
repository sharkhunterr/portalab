"""Spec 005 fixtures: a Connectors module on the full platform with isolated registries and a fake backend."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.automation_actions import ActionRegistry
from portalab.capabilities.connector_sdk import ConnectorRegistry
from portalab.capabilities.isolation import IsolationPolicy
from portalab.capabilities.record_sink import SinkRegistry
from portalab.capabilities.record_sink_testkit import InMemoryRecordSink
from portalab.connectors.fake import BACKENDS, CAPABILITY, FakeBackend, FakeConnector, backend
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.secrets import SecretBox
from portalab.core.time import Clock
from portalab.modules.connectors.module import ConnectorsModule
from portalab.modules.connectors.services.manager import ManagerHooks
from portalab.modules.connectors.settings import ConnectorsConfig
from portalab.modules.identity.services.credentials import set_password
from tests.authz_fixtures import TEST_APPLICATION_KEY, insert_user, make_admin
from tests.integration.identity.helpers import PASSWORD, login, module_of
from tests.privacy_fixtures import FullPlatform, make_full_platform

TOKEN = "fake-credential"


@dataclass
class ConnectorsHarness:
    full: FullPlatform
    module: ConnectorsModule
    connectors: ConnectorRegistry
    sinks: SinkRegistry
    actions: ActionRegistry
    sink: InMemoryRecordSink
    admin: Principal
    base_url: str

    @property
    def remote(self) -> FakeBackend:
        return backend(self.base_url)

    async def configure(self, name: str = "Fake", *, base_url: str | None = None, token: str = TOKEN) -> UUID:
        return await self.module.manager.configure(
            self.admin,
            connector_key="fake",
            name=name,
            config={"base_url": base_url or self.base_url},
            secrets={"api_token": token},
        )

    async def enabled(self, name: str = "Fake", *, base_url: str | None = None) -> UUID:
        service_id = await self.configure(name, base_url=base_url)
        await self.module.manager.enable(self.admin, service_id)
        return service_id

    async def outbox(self, prefix: str) -> list[dict[str, Any]]:
        async with self.full.database.session() as session:
            rows = await session.execute(
                text("SELECT type, metadata FROM core.event_outbox WHERE type LIKE :p ORDER BY seq"),
                {"p": f"{prefix}%"},
            )
            return [{"type": row[0], **(row[1] or {})} for row in rows]


async def admin_client(app: FastAPI, client: httpx.AsyncClient, cn: ConnectorsHarness) -> None:
    """Give the harness Admin a password and sign the client in as that Admin."""
    identity = module_of(app)
    async with cn.full.database.unit_of_work() as uow:
        assert cn.admin.user_id is not None
        await set_password(uow.session, identity.hasher, cn.admin.user_id, PASSWORD, identity.ctx.now())
    response = await login(client, "admin")
    assert response.status_code == 200, response.text


async def make_connectors(
    database: Database, blob_root: Path, clock: Clock | None = None, *, config: ConnectorsConfig | None = None
) -> ConnectorsHarness:
    full = make_full_platform(database, blob_root, clock)
    await full.authz.catalog.sync()
    connectors, sinks, actions = ConnectorRegistry(), SinkRegistry(), ActionRegistry()
    connectors.register(FakeConnector(), owner="test:connectors")
    sink = InMemoryRecordSink()
    sinks.register(CAPABILITY, sink, owner="test:connectors")
    module = ConnectorsModule(
        database,
        full.authz.engine.events,
        full.authz.audit,
        full.identity.capabilities,
        SecretBox(TEST_APPLICATION_KEY),
        authorizer=full.authz.engine,
        connectors=connectors,
        sinks=sinks,
        actions=actions,
        config=config or ConnectorsConfig(http_timeout_seconds=0.2, circuit_failure_threshold=2),
        clock=clock,
        hooks=ManagerHooks(isolation=IsolationPolicy(timeout_seconds=0.3, max_retries=0)),
    )
    module.register_capabilities()
    admin_id = await insert_user(database, "admin")
    await make_admin(full, admin_id)
    base_url = f"http://fake-{uuid4().hex[:8]}.lan"
    BACKENDS[base_url] = FakeBackend()
    return ConnectorsHarness(
        full, module, connectors, sinks, actions, sink, Principal(user_id=admin_id), base_url
    )
