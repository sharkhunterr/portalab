"""Reusable ``ChangeSummaryProvider`` conformance helper (spec 009 T029). A domain proves its provider::

    class TestNewsChanges(ChangeSummaryContractKit):
        async def make_world(self) -> SummaryWorld: ...  # provider, principals, private item

Checks: items are strictly after ``since``; ``limit`` honoured; a principal without access gets nothing;
another user's private item never appears for someone else; titles are text or catalog keys (no markup).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from portalab.capabilities.dashboard import ChangeSummaryProvider
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal


@dataclass
class SummaryWorld:
    provider: ChangeSummaryProvider
    allowed: Principal
    denied: Principal
    since: datetime
    private_ref_of_other: str | None = None  # a ref that must never appear for ``allowed``
    produce: Callable[[], Awaitable[None]] | None = None  # create fresh changes after ``since``


class ChangeSummaryContractKit:
    ctx = LocaleContext()

    async def make_world(self) -> SummaryWorld:
        raise NotImplementedError

    async def test_after_since_and_limited(self) -> None:
        world = await self.make_world()
        if world.produce is not None:
            await world.produce()
        items = await world.provider.changes_since(world.allowed, world.since, 1, self.ctx)
        assert len(items) <= 1
        assert all(item.occurred_at > world.since for item in items)
        future = await world.provider.changes_since(
            world.allowed, world.since + timedelta(days=3650), 10, self.ctx
        )
        assert list(future) == []

    async def test_scoped_by_principal(self) -> None:
        world = await self.make_world()
        assert list(await world.provider.changes_since(world.denied, world.since, 50, self.ctx)) == []
        refs = {
            item.ref for item in await world.provider.changes_since(world.allowed, world.since, 50, self.ctx)
        }
        if world.private_ref_of_other is not None:
            assert world.private_ref_of_other not in refs

    async def test_titles_are_plain(self) -> None:
        world = await self.make_world()
        for item in await world.provider.changes_since(world.allowed, world.since, 50, self.ctx):
            assert item.title_key or item.title
            assert "<" not in (item.title or "")
