"""Support integration fixtures: the support module on the full platform with isolated registries and a
fake service directory."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.automation_actions import ActionRegistry
from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.events import EventTypeRegistry
from portalab.capabilities.health import SERVICE_DIRECTORY, ServiceInfo
from portalab.capabilities.notifications import NOTIFY, CommunicationRef, CommunicationRequest
from portalab.capabilities.observability import ObservableRegistry
from portalab.capabilities.search import SearchRegistry
from portalab.core.authz_port import Principal
from portalab.core.blobstore import FileSystemBlobStore
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.support.module import SupportModule
from tests.integration.privacy.conftest import NOW
from tests.privacy_fixtures import FullPlatform, make_full_platform


class FakeDirectory:
    async def services(self) -> list[ServiceInfo]:
        return [
            ServiceInfo(id="s1", name="Media", connector="jellyfin", state="enabled"),
            ServiceInfo(id="s2", name="Books", connector="kavita", state="enabled"),
        ]

    async def service(self, service_id: str) -> ServiceInfo | None:
        return None


class Outbox:
    """Records ``notifications.send`` requests."""

    def __init__(self) -> None:
        self.sent: list[CommunicationRequest] = []

    async def send(
        self, request: CommunicationRequest, *, caller: Principal | None = None
    ) -> CommunicationRef:
        self.sent.append(request)
        return CommunicationRef(uuid4(), True, 1)


@dataclass
class SupportHarness:
    full: FullPlatform
    module: SupportModule
    widgets: WidgetRegistry
    search: SearchRegistry
    actions: ActionRegistry = field(default_factory=ActionRegistry)
    outbox: Outbox = field(default_factory=Outbox)
    people: dict[str, UUID] = field(default_factory=dict)

    def p(self, name: str) -> Principal:
        return Principal(user_id=self.people[name])


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def support(database: Database, tmp_path: Path, clock: FixedClock) -> SupportHarness:
    full = make_full_platform(database, tmp_path / "blobs", clock)
    await full.authz.catalog.sync()
    widgets, search, actions, outbox = WidgetRegistry(), SearchRegistry(), ActionRegistry(), Outbox()
    capabilities = full.identity.capabilities
    capabilities.provide(NOTIFY, outbox, instance_ref="test-outbox", owner="test")
    module = SupportModule(
        database,
        full.authz.engine.events,
        full.authz.audit,
        capabilities,
        full.authz.engine,
        clock=clock,
        widgets=widgets,
        search=search,
        event_types=EventTypeRegistry(),
        observables=ObservableRegistry(),
        actions=actions,
        blobs=FileSystemBlobStore(tmp_path / "support-blobs"),
    )
    module.register()
    await module.definitions.ensure_baseline()
    capabilities.provide(SERVICE_DIRECTORY, FakeDirectory(), instance_ref="t", owner="module:connectors")
    return SupportHarness(full, module, widgets, search, actions, outbox)


@pytest.fixture
def app(support: SupportHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = support.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        support=support.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http


@pytest.fixture
async def people(app: FastAPI, support: SupportHarness) -> dict[str, UUID]:
    """``boss`` (admin), ``sam`` (support), ``mona`` (moderator), ``ursula`` and ``ulrich`` (users)."""
    from tests.authz_fixtures import make_admin
    from tests.integration.identity.helpers import create_user, module_of

    out = {
        name: await create_user(module_of(app), name) for name in ("boss", "sam", "mona", "ursula", "ulrich")
    }
    await make_admin(support.full, out["boss"])
    admin = Principal(user_id=out["boss"])
    await support.full.authz.grants.assign_role(admin, out["sam"], "support")
    await support.full.authz.grants.assign_role(admin, out["mona"], "moderator")
    support.people = out
    return out
