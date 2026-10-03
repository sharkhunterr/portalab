"""Notifications integration fixtures: the notifications module on the real event store, with i18n
rendering, isolated registries and a recording e-mail transport."""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.automation_actions import ActionRegistry
from portalab.capabilities.events import EventType
from portalab.capabilities.notifications import CategoryRegistry, EmailMessage
from portalab.capabilities.observability import ObservableRegistry
from portalab.capabilities.service_events import STATUS_CHANGED_TYPE
from portalab.core.db import Database
from portalab.core.event_port import SubjectRef
from portalab.core.time import FixedClock
from portalab.modules.i18n.catalog.plugins import PluginCatalogs
from portalab.modules.i18n.content.localizer import ContentKinds
from portalab.modules.i18n.module import I18nModule
from portalab.modules.notifications.module import NotificationsModule
from tests.events_fixtures import EventsHarness, make_events
from tests.integration.privacy.conftest import NOW


class Outbox:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.fail = 0  # number of next sends to fail

    async def send(self, message: EmailMessage) -> None:
        if self.fail:
            self.fail -= 1
            raise ConnectionRefusedError("smtp down")
        self.sent.append(message)


@dataclass
class NotifyHarness:
    ev: EventsHarness
    module: NotificationsModule
    categories: CategoryRegistry
    actions: ActionRegistry
    mail: Outbox = field(default_factory=Outbox)

    @property
    def database(self) -> Database:
        return self.ev.full.database

    async def publish(
        self, event_type: str, payload: Mapping[str, Any], *, at: datetime, subject: SubjectRef | None = None
    ) -> None:
        async with self.database.unit_of_work() as uow:
            await self.ev.publisher.publish(
                uow.session, event_type, dict(payload), occurred_at=at, subject=subject, source="test"
            )

    async def dispatch(self) -> None:
        for _ in range(10):
            runs = await self.ev.module.dispatcher.run_once()
            if not any(run.delivered for run in runs):
                return


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def notify(database: Database, tmp_path: Path, clock: FixedClock) -> NotifyHarness:
    ev = make_events(database, tmp_path / "blobs", clock)
    await ev.full.authz.catalog.sync()
    ev.module.register()
    capabilities = ev.full.identity.capabilities
    i18n = I18nModule(
        database,
        ev.publisher,
        ev.full.authz.audit,
        capabilities,
        clock=clock,
        plugins=PluginCatalogs(),
        content_kinds=ContentKinds(),
        event_types=ev.types,
        consumers=ev.consumers,
        observables=ObservableRegistry(),
    )
    i18n.register()
    for name in (
        "maintenance.scheduled",
        "maintenance.rescheduled",
        "maintenance.started",
        "maintenance.ended",
        "maintenance.cancelled",
    ):
        ev.types.register(EventType(name, "module:health"))
    for name in ("user.suspended", "user.reactivated", "user.deletion_requested"):
        ev.types.register(EventType(name, "module:identity"))
    ev.types.register(STATUS_CHANGED_TYPE)
    mail = Outbox()
    categories, actions = CategoryRegistry(), ActionRegistry()
    module = NotificationsModule(
        database,
        ev.publisher,
        ev.full.authz.audit,
        capabilities,
        ev.full.authz.engine,
        clock=clock,
        categories=categories,
        event_types=ev.types,
        consumers=ev.consumers,
        observables=ObservableRegistry(),
        actions=actions,
        transport=mail,
    )
    module.register()
    return NotifyHarness(ev, module, categories, actions, mail)


@pytest.fixture
def app(notify: NotifyHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = notify.ev.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        notifications=notify.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http
