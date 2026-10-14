"""Issue 122 — service signals: a service's data watched for automations. A change (or a first « true »)
publishes ``service.signal_changed`` once; the parity presets show a banner while a server checks its
parity and take it down when the check is over; nothing is read while no automation listens."""

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import text

from portalab.capabilities.health import INFRA_HOST, HostReport
from portalab.capabilities.notifications import CategoryRegistry
from portalab.capabilities.observability import ObservableRegistry
from portalab.capabilities.service_signals import Signal, SignalRegistry, Value
from portalab.modules.automations.signals import SignalWatcher
from portalab.modules.automations.templates.loader import load
from portalab.modules.notifications.module import NotificationsModule
from tests.integration.automations.conftest import AutoHarness

pytestmark = pytest.mark.integration


class Server:
    def __init__(self) -> None:
        self.parity: bool | None = False
        self.reads = 0

    async def report(self) -> HostReport:
        return HostReport()


async def banners(au: AutoHarness) -> list[tuple[str, str, bool]]:
    async with au.database.session() as session:
        rows = await session.execute(
            text("SELECT tag, title, ended_at IS NULL FROM notify.announcements ORDER BY created_at")
        )
        return [(r[0], r[1], r[2]) for r in rows]


async def test_parity_check_shows_then_ends_a_banner(au: AutoHarness) -> None:
    notifications = NotificationsModule(
        au.database,
        au.ev.publisher,
        au.ev.full.authz.audit,
        au.ev.full.identity.capabilities,
        au.ev.full.authz.engine,
        clock=au.clock,
        categories=CategoryRegistry(),
        event_types=au.ev.types,
        consumers=au.ev.consumers,
        observables=ObservableRegistry(),
        actions=au.actions,
    )
    notifications.register()
    server = Server()
    au.ev.full.identity.capabilities.provide(INFRA_HOST, server, instance_ref="srv1", owner="module:test")

    async def parity(_service: str, provider: Any) -> Value | None:
        provider.reads += 1
        return provider.parity

    registry = SignalRegistry()
    registry.register(Signal("infrastructure.parity_running", "module:test", INFRA_HOST, "bool", parity))
    watcher = SignalWatcher(
        au.database, au.ev.publisher, au.ev.full.identity.capabilities, au.module._listened,
        registry=registry, clock=au.clock,
    )  # fmt: skip

    assert await watcher.run() == 0 and server.reads == 0  # no automation listens: nothing is read
    for key in ("parity-check-banner", "parity-check-banner-end"):
        preset = next(t for t in load() if t.key == key)
        await au.automation(key, preset.definition)
    au.module.triggers.invalidate()

    assert await watcher.run() == 0  # first sight, no check under way: nothing to tell
    server.parity = True
    au.clock.advance(timedelta(minutes=1))
    assert await watcher.run() == 1
    await au.dispatch()
    assert await banners(au) == [("parity-srv1", "Parity check under way on srv1", True)]
    au.clock.advance(timedelta(minutes=1))
    assert await watcher.run() == 0  # still running: no change, no second banner
    server.parity = None
    au.clock.advance(timedelta(minutes=1))
    assert await watcher.run() == 0  # the server did not answer: unknown is never a change
    server.parity = False
    au.clock.advance(timedelta(minutes=1))
    assert await watcher.run() == 1
    await au.dispatch()
    assert await banners(au) == [("parity-srv1", "Parity check under way on srv1", False)]
    current = await watcher.current()
    assert [(c["signal"], c["service_id"], c["value"]) for c in current] == [
        ("infrastructure.parity_running", "srv1", False)
    ]
