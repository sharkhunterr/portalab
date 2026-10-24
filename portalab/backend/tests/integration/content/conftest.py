"""Content integration fixtures (spec 011): news, wiki, calendar and the content helper on the real event
store, with isolated registries, an editor, a reader and an administrator."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.automation_actions import ActionRegistry
from portalab.capabilities.content import CalendarSourceRegistry, LinkResolverRegistry
from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.notifications import (
    NOTIFY,
    CategoryRegistry,
    CommunicationRef,
    CommunicationRequest,
)
from portalab.capabilities.observability import ObservableRegistry
from portalab.capabilities.search import SearchRegistry
from portalab.core.authz_port import Principal
from portalab.core.blobstore import FileSystemBlobStore
from portalab.core.db import Database
from portalab.core.time import FixedClock
from portalab.modules.calendar.module import CalendarModule
from portalab.modules.content.module import ContentModule
from portalab.modules.news.module import NewsModule
from portalab.modules.wiki.module import WikiModule
from tests.authz_fixtures import make_admin
from tests.events_fixtures import EventsHarness, make_events
from tests.integration.identity.helpers import create_user, module_of
from tests.integration.privacy.conftest import NOW


class Outbox:
    """Records ``notifications.send`` requests (010's real module is not needed here)."""

    def __init__(self) -> None:
        self.sent: list[CommunicationRequest] = []
        self.keys: set[str] = set()

    async def send(
        self, request: CommunicationRequest, *, caller: Principal | None = None
    ) -> CommunicationRef:
        from uuid import uuid4

        created = request.dedup_key not in self.keys
        if created:
            self.keys.add(request.dedup_key)
            self.sent.append(request)
        return CommunicationRef(uuid4(), created, 1)


@dataclass
class ContentHarness:
    ev: EventsHarness
    content: ContentModule
    wiki: WikiModule
    news: NewsModule
    calendar: CalendarModule
    resolvers: LinkResolverRegistry
    sources: CalendarSourceRegistry
    search: SearchRegistry
    actions: ActionRegistry
    outbox: Outbox
    people: dict[str, UUID] = field(default_factory=dict)

    @property
    def database(self) -> Database:
        return self.ev.full.database

    def p(self, name: str) -> Principal:
        return Principal(user_id=self.people[name])


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def ct(database: Database, tmp_path: Path, clock: FixedClock) -> ContentHarness:
    ev = make_events(database, tmp_path / "blobs", clock)
    await ev.full.authz.catalog.sync()
    ev.module.register()
    caps = ev.full.identity.capabilities
    engine = ev.full.authz.engine
    resolvers, sources, search = LinkResolverRegistry(), CalendarSourceRegistry(), SearchRegistry()
    widgets, categories, actions = WidgetRegistry(), CategoryRegistry(), ActionRegistry()
    outbox = Outbox()
    caps.provide(NOTIFY, outbox, instance_ref="test-outbox", owner="test")
    content = ContentModule(
        database,
        caps,
        engine,
        blobs=FileSystemBlobStore(tmp_path / "content"),
        resolvers=resolvers,
        clock=clock,
    )
    content.register()
    wiki = WikiModule(
        database, ev.publisher, ev.full.authz.audit, caps, engine, clock=clock, event_types=ev.types,
        resolvers=resolvers, search=search, observables=ObservableRegistry(),
    )  # fmt: skip
    wiki.register()
    news = NewsModule(
        database, ev.publisher, ev.full.authz.audit, caps, engine, clock=clock, event_types=ev.types,
        resolvers=resolvers, calendar=sources, search=search, widgets=widgets, categories=categories,
        actions=actions, observables=ObservableRegistry(),
    )  # fmt: skip
    news.register()
    calendar = CalendarModule(
        database, ev.publisher, caps, engine, clock=clock, sources=sources, event_types=ev.types,
        widgets=widgets, categories=categories, observables=ObservableRegistry(), search=search,
    )  # fmt: skip
    calendar.register()
    return ContentHarness(ev, content, wiki, news, calendar, resolvers, sources, search, actions, outbox)


@pytest.fixture
def app(ct: ContentHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = ct.ev.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        content=ct.content,
        wiki=ct.wiki,
        news=ct.news,
        calendar=ct.calendar,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http


@pytest.fixture
async def people(app: FastAPI, ct: ContentHarness) -> dict[str, UUID]:
    """``boss`` (admin), ``eddie`` (editor), ``rita`` (reader), ``sam`` (support role)."""
    out = {name: await create_user(module_of(app), name) for name in ("boss", "eddie", "rita", "sam")}
    await make_admin(ct.ev.full, out["boss"])
    admin = Principal(user_id=out["boss"])
    await ct.ev.full.authz.grants.assign_role(admin, out["eddie"], "editor")
    await ct.ev.full.authz.grants.assign_role(admin, out["sam"], "support")
    ct.people = out
    return out
